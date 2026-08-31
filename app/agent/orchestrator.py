import json
import time
from typing import Any

from google import genai
from google.genai import types
from pydantic import ValidationError
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.agent.resolution import (
    derive_resolution,
    guard_customer_response,
    reconcile_resolution_with_model_response,
)
from app.agent.schemas import (
    CustomerLookupInput,
    KnowledgeSearchInput,
    PaymentLookupInput,
    ServiceStatusInput,
    SubscriptionLookupInput,
)
from app.config import settings
from app.db.models import (
    AgentRun,
    Conversation,
    Customer,
    Message,
    ToolExecution,
)
from app.db.schema import ensure_schema
from app.db.session import SessionLocal
from app.tools.customer import get_customer
from app.tools.knowledge import search_knowledge_base
from app.tools.payment import get_payment_status
from app.tools.service_status import get_service_status
from app.tools.subscription import get_subscription


PROMPT_VERSION = "v2-multi-tool-2"
CONVERSATION_CONTEXT_VERSION = "v2-recent-context-1"
RECENT_CONTEXT_MESSAGE_LIMIT = 8


class ConversationCustomerMismatchError(ValueError):
    pass


SYSTEM_PROMPT = """
You are Support Pilot, the AI customer-support agent for CloudDesk.

Your role is limited to CloudDesk customer support.

Core rules:
1. Never invent customer, subscription, payment, service-status, policy,
   incident, account, billing, or support information.
2. Account-specific facts must come from approved tools.
3. Policy and documentation answers must come from search_knowledge_base.
4. If an active customer_id is provided, use that exact ID when an
   account-specific tool requires it.
5. Use get_customer for customer identity and account-status questions.
6. Use get_subscription for current plan, requested plan, subscription status,
   or subscription synchronization state.
7. Use get_payment_status for payment, charge, transaction, billing-payment,
   or plan-purchase status questions.
8. Use get_service_status for outage or service-health questions.
9. Use search_knowledge_base for documented CloudDesk policies and support
   guidance.
10. Do not claim that unsupported or state-changing actions have been completed.
11. If account-specific information is required and no customer_id is available,
    ask the customer for their CloudDesk customer ID. Never invent an ID.
12. If a tool reports that a record is unavailable or not found, clearly say
    that the information could not be found. Never replace missing information
    with a guess.
13. If the customer's request is unrelated to CloudDesk products, accounts,
    subscriptions, billing, service availability, policies, or support,
    politely explain that it is outside Support Pilot's support scope.
14. Do not use CloudDesk tools for unrelated questions.
15. Never expose another customer's information.

Cross-system investigation rules:
16. A tool result is authoritative only for the business system that produced
    it. Do not silently override conflicting evidence from another system.
17. For upgrade or billing mismatches, collect the evidence needed to compare
    subscription state and payment state before making a conclusion.
18. If payment succeeded but the requested plan is not applied, do not claim
    the upgrade completed successfully. Explain the mismatch and avoid claiming
    that Support Pilot changed the account.
19. In get_payment_status results, the top-level status describes whether the
    tool lookup succeeded. payment_status describes the actual payment outcome.
    Never interpret status=SUCCESS as proof that the payment itself succeeded.
20. A NOT_FOUND, NOT_READY, or ERROR result is not a negative business fact and
    must not be presented as proof that an event did not happen.
21. If multiple tools are needed, continue investigating until enough evidence
    is available or the maximum step limit is reached.

Knowledge-grounding rules:
22. search_knowledge_base performs semantic retrieval. Its returned passages
    are candidate evidence, not automatic proof that the customer's requested
    fact is true or false.
23. A similarity score only measures semantic closeness. Never treat a high
    score as confirmation that a passage answers the customer's exact question.
24. Before stating a policy, feature, payment method, plan type, limitation,
    eligibility rule, or other documented fact, verify that at least one
    retrieved passage explicitly states or directly supports that claim.
25. Do not infer a negative fact merely because the retrieved passages fail to
    mention something. Missing documentation means the answer is unknown from
    the available knowledge base; it does not mean the feature, policy, or
    option does not exist.
26. If the retrieved passages are related to the general topic but do not
    actually answer the customer's question, say that the available CloudDesk
    documentation does not provide enough information to confirm the answer.
27. For yes/no policy questions, answer yes or no only when the retrieved
    evidence explicitly supports that conclusion. Otherwise use uncertainty
    language such as: "I don't have documented information confirming that."
28. If search_knowledge_base returns NOT_FOUND, NOT_READY, or ERROR, do not
    infer an answer from general knowledge or from the absence of a result.
29. Example: if a customer asks whether CloudDesk offers a lifetime
    subscription and the retrieved passages discuss refunds, billing cycles,
    or upgrades but never mention lifetime subscriptions, do not say that
    CloudDesk does not offer one. Say that the available documentation does not
    confirm whether a lifetime subscription is offered.
30. Example: if a customer asks whether CloudDesk accepts Bitcoin and the
    retrieved passages do not explicitly document cryptocurrency payment
    support, do not claim that CloudDesk accepts or rejects Bitcoin. Say that
    the available documentation does not confirm it.

Recent-conversation rules:
31. Recent messages from the SAME conversation may be supplied before the
    current customer message. Use them only to understand follow-up references
    such as "why did it fail?", "check that again", "what about that payment?",
    and similar conversational references.
32. Previous assistant messages are conversation context, not authoritative
    business-system evidence. If a follow-up requires current customer,
    subscription, payment, service, or policy facts, call the appropriate
    approved tool again.
33. A customer_id recovered from the active persisted conversation may be used
    for account-specific tools in that same conversation.
34. Never carry customer information, messages, issue state, or conclusions
    between different conversation IDs.
35. If the recent conversation still does not make the follow-up clear enough
    to investigate safely, ask a focused clarification question instead of
    guessing.
"""


GET_CUSTOMER = types.FunctionDeclaration(
    name="get_customer",
    description=(
        "Retrieve customer identity and account status. "
        "Use for account-specific customer information."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "customer_id": {
                "type": "string",
                "description": "CloudDesk customer ID, for example CUS-1001.",
            }
        },
        "required": ["customer_id"],
    },
)


GET_SUBSCRIPTION = types.FunctionDeclaration(
    name="get_subscription",
    description=(
        "Retrieve the customer's current subscription plan and subscription "
        "state. Use when the customer asks about their current plan, requested "
        "plan, subscription status, or subscription state."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "customer_id": {
                "type": "string",
                "description": "CloudDesk customer ID, for example CUS-1007.",
            }
        },
        "required": ["customer_id"],
    },
)


GET_PAYMENT_STATUS = types.FunctionDeclaration(
    name="get_payment_status",
    description=(
        "Retrieve a CloudDesk customer's payment status. Use for payment, "
        "charge, transaction, billing-payment, or paid-plan questions. If "
        "payment_id is omitted, the latest payment for that customer is returned."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "customer_id": {
                "type": "string",
                "description": "CloudDesk customer ID, for example CUS-1007.",
            },
            "payment_id": {
                "type": "string",
                "description": "Optional CloudDesk payment ID, for example PAY-3007.",
            },
        },
        "required": ["customer_id"],
    },
)


GET_SERVICE_STATUS = types.FunctionDeclaration(
    name="get_service_status",
    description=(
        "Check active CloudDesk service incidents or outages. "
        "Use when a customer reports service availability problems."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "service": {
                "type": "string",
                "description": (
                    "CloudDesk service name. Use core for the main "
                    "CloudDesk application."
                ),
            },
            "region": {
                "type": "string",
                "description": "Optional service region such as IN or EU.",
            },
        },
    },
)


SEARCH_KNOWLEDGE_BASE = types.FunctionDeclaration(
    name="search_knowledge_base",
    description=(
        "Search official CloudDesk support documentation and policies. "
        "Use for refund policy, plan policy, troubleshooting guidance, "
        "support scope, and other documented CloudDesk support questions. "
        "Returned passages are semantic-retrieval candidates; similarity "
        "scores indicate closeness, not factual proof. Base an answer only "
        "on claims explicitly supported by the returned passage content."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The CloudDesk support question to search for.",
            },
            "top_k": {
                "type": "integer",
                "description": "Maximum number of passages to return.",
                "minimum": 1,
                "maximum": 10,
            },
        },
        "required": ["query"],
    },
)


V1_TOOL = types.Tool(
    function_declarations=[
        GET_CUSTOMER,
        GET_SUBSCRIPTION,
        GET_SERVICE_STATUS,
        SEARCH_KNOWLEDGE_BASE,
    ]
)


V2_TOOL = types.Tool(
    function_declarations=[
        GET_CUSTOMER,
        GET_SUBSCRIPTION,
        GET_PAYMENT_STATUS,
        GET_SERVICE_STATUS,
        SEARCH_KNOWLEDGE_BASE,
    ]
)


def _execute_tool(
    db: Session,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate Gemini arguments and execute one approved Support Pilot tool.
    """

    try:
        if tool_name == "get_customer":
            payload = CustomerLookupInput(**arguments)

            return get_customer(
                db,
                payload,
            ).model_dump(mode="json")

        if tool_name == "get_subscription":
            payload = SubscriptionLookupInput(**arguments)

            return get_subscription(
                db,
                payload,
            ).model_dump(mode="json")

        if tool_name == "get_payment_status":
            payload = PaymentLookupInput(**arguments)

            return get_payment_status(
                db,
                payload,
            ).model_dump(mode="json")

        if tool_name == "get_service_status":
            payload = ServiceStatusInput(**arguments)

            return get_service_status(
                db,
                payload,
            ).model_dump(mode="json")

        if tool_name == "search_knowledge_base":
            payload = KnowledgeSearchInput(**arguments)

            return search_knowledge_base(
                db,
                payload,
            ).model_dump(mode="json")

        return {
            "status": "ERROR",
            "error": f"Unsupported tool requested: {tool_name}",
        }

    except ValidationError as exc:
        return {
            "status": "ERROR",
            "error": f"Invalid tool arguments: {exc}",
        }

    except Exception as exc:
        return {
            "status": "ERROR",
            "error": f"{type(exc).__name__}: {exc}",
        }


def _intent_from_tool(
    tool_name: str,
) -> str:
    """
    Convert tool selection into a simple support intent.
    """

    intent_map = {
        "get_customer": "customer_account",
        "get_subscription": "subscription",
        "get_payment_status": "payment",
        "get_service_status": "service_status",
        "search_knowledge_base": "knowledge",
    }

    return intent_map.get(
        tool_name,
        "unknown",
    )


def _get_or_create_conversation(
    db: Session,
    conversation_id: str | None,
    customer_id: str | None,
) -> Conversation:
    """
    Load an existing conversation or create a new one.
    """

    if conversation_id:
        conversation = db.get(
            Conversation,
            conversation_id,
        )

        if conversation is None:
            raise ValueError(
                f"Conversation not found: {conversation_id}"
            )

        if (
            customer_id
            and conversation.customer_id
            and conversation.customer_id != customer_id
        ):
            raise ConversationCustomerMismatchError(
                "The supplied customer_id does not match this conversation."
            )

        if (
            customer_id
            and conversation.customer_id is None
            and db.get(Customer, customer_id) is not None
        ):
            conversation.customer_id = customer_id

        return conversation

    persisted_customer_id = None

    if (
        customer_id
        and db.get(Customer, customer_id) is not None
    ):
        persisted_customer_id = customer_id

    conversation = Conversation(
        customer_id=persisted_customer_id,
    )

    db.add(conversation)
    db.flush()

    return conversation



def _load_recent_conversation_messages(
    db: Session,
    conversation_id: str,
    limit: int = RECENT_CONTEXT_MESSAGE_LIMIT,
) -> list[Message]:
    """
    Load a bounded recent user/assistant history for one conversation only.

    The current user message is persisted after this function runs, preventing
    the newest message from being duplicated in Gemini context.
    """

    if limit <= 0:
        return []

    role_order = case(
        (
            Message.role == "user",
            0,
        ),
        (
            Message.role == "assistant",
            1,
        ),
        else_=2,
    )

    recent_desc = list(
        db.scalars(
            select(
                Message
            )
            .where(
                Message.conversation_id
                == conversation_id,
                Message.role.in_(
                    [
                        "user",
                        "assistant",
                    ]
                ),
            )
            .order_by(
                Message.created_at.desc(),
                role_order.desc(),
                Message.message_id.desc(),
            )
            .limit(limit)
        ).all()
    )

    recent_desc.reverse()

    return recent_desc


def _history_message_to_content(
    message: Message,
) -> types.Content:
    """
    Convert a persisted Support Pilot message into Gemini conversation format.
    """

    gemini_role = (
        "model"
        if message.role == "assistant"
        else "user"
    )

    return types.Content(
        role=gemini_role,
        parts=[
            types.Part.from_text(
                text=message.content
            )
        ],
    )


def _build_current_user_context(
    message: str,
    effective_customer_id: str | None,
    conversation: Conversation,
) -> str:
    """
    Add small pieces of persisted V2 conversation state to the current turn.

    This state helps resolve follow-up language. It does not replace approved
    business tools as the source of truth.
    """

    active_customer = (
        effective_customer_id
        or "NOT_PROVIDED"
    )

    current_issue = (
        conversation.current_issue
        or "NOT_IDENTIFIED"
    )

    previous_resolution = (
        conversation.resolution_status
        or "NOT_SET"
    )

    return (
        f"Active customer_id: {active_customer}\n"
        f"Conversation issue: {current_issue}\n"
        f"Previous resolution status: {previous_resolution}\n"
        f"Customer message: {message}"
    )


def _build_conversation_contents(
    history: list[Message],
    current_user_context: str,
) -> list[types.Content]:
    """
    Build Gemini contents from bounded same-conversation history plus the
    current customer turn.
    """

    contents = [
        _history_message_to_content(
            history_message
        )
        for history_message in history
    ]

    contents.append(
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(
                    text=current_user_context
                )
            ],
        )
    )

    return contents


def run_agent(
    message: str,
    customer_id: str | None = None,
    conversation_id: str | None = None,
    max_steps: int | None = None,
) -> dict[str, Any]:
    """
    Run the V2 native Gemini tool-calling loop with bounded recent conversation context.

    Persists:
    - conversation
    - user message
    - assistant message
    - agent run
    - tool executions
    """

    ensure_schema()

    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured."
        )

    if max_steps is None:
        max_steps = settings.max_agent_steps

    if max_steps < 1:
        raise ValueError(
            "max_steps must be at least 1."
        )

    client = genai.Client(
        api_key=settings.gemini_api_key
    )

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[V2_TOOL],
        automatic_function_calling=(
            types.AutomaticFunctionCallingConfig(
                disable=True
            )
        ),
    )

    trace: list[dict[str, Any]] = [
        {
            "step": 0,
            "type": "request",
            "customer_id": customer_id,
            "message": message,
        }
    ]

    run_started = time.perf_counter()

    with SessionLocal() as db:
        conversation = _get_or_create_conversation(
            db=db,
            conversation_id=conversation_id,
            customer_id=customer_id,
        )

        persisted_conversation_id = (
            conversation.conversation_id
        )

        effective_customer_id = (
            customer_id
            or conversation.customer_id
        )

        recent_history = (
            _load_recent_conversation_messages(
                db=db,
                conversation_id=(
                    persisted_conversation_id
                ),
            )
        )

        current_user_context = (
            _build_current_user_context(
                message=message,
                effective_customer_id=(
                    effective_customer_id
                ),
                conversation=conversation,
            )
        )

        contents = (
            _build_conversation_contents(
                history=recent_history,
                current_user_context=(
                    current_user_context
                ),
            )
        )

        trace[0]["customer_id"] = (
            effective_customer_id
        )

        if recent_history:
            trace.append(
                {
                    "step": 0,
                    "type": (
                        "conversation_context"
                    ),
                    "context_version": (
                        CONVERSATION_CONTEXT_VERSION
                    ),
                    "messages_loaded": len(
                        recent_history
                    ),
                    "customer_id": (
                        effective_customer_id
                    ),
                    "current_issue": (
                        conversation.current_issue
                    ),
                    "previous_resolution_status": (
                        conversation.resolution_status
                    ),
                }
            )

        db.add(
            Message(
                conversation_id=(
                    conversation.conversation_id
                ),
                role="user",
                content=message,
            )
        )

        agent_run = AgentRun(
            conversation_id=(
                conversation.conversation_id
            ),
            prompt_version=PROMPT_VERSION,
            request_message=message,
        )

        db.add(agent_run)

        db.commit()

        run_id = agent_run.run_id

        detected_intent: str | None = None

        seen_tool_calls: set[str] = set()

        try:
            for step_number in range(
                1,
                max_steps + 1,
            ):
                response = (
                    client.models.generate_content(
                        model=settings.gemini_model,
                        contents=contents,
                        config=config,
                    )
                )

                function_calls = (
                    response.function_calls
                    or []
                )

                if not function_calls:
                    final_text = (
                        response.text
                        or ""
                    ).strip()

                    if detected_intent is None:
                        detected_intent = "general"

                    resolution = derive_resolution(
                        trace
                    )

                    resolution = (
                        reconcile_resolution_with_model_response(
                            resolution=resolution,
                            model_response=final_text,
                        )
                    )

                    resolution_data = None

                    if resolution is not None:
                        resolution_data = (
                            resolution.model_dump(
                                mode="json"
                            )
                        )

                        trace.append(
                            {
                                "step": step_number,
                                "type": "resolution",
                                **resolution_data,
                            }
                        )

                        agent_run.resolution_status = (
                            resolution.resolution_status
                        )

                        agent_run.issue_type = (
                            resolution.issue_type
                        )

                        agent_run.resolution_summary = (
                            resolution.summary
                        )

                        conversation.resolution_status = (
                            resolution.resolution_status
                        )

                        conversation.current_issue = (
                            resolution.issue_type
                        )

                    model_final_text = final_text

                    final_text = (
                        guard_customer_response(
                            model_response=(
                                model_final_text
                            ),
                            resolution=resolution,
                            customer_message=message,
                        )
                    )

                    if final_text != model_final_text:
                        trace.append(
                            {
                                "step": step_number,
                                "type": (
                                    "response_guardrail"
                                ),
                                "resolution_status": (
                                    resolution.resolution_status
                                    if resolution
                                    else None
                                ),
                                "issue_type": (
                                    resolution.issue_type
                                    if resolution
                                    else None
                                ),
                                "reason": (
                                    "Deterministic safety wording "
                                    "replaced the model response."
                                ),
                            }
                        )

                    trace.append(
                        {
                            "step": step_number,
                            "type": "final_response",
                            "intent": detected_intent,
                            "response": final_text,
                        }
                    )

                    db.add(
                        Message(
                            conversation_id=(
                                persisted_conversation_id
                            ),
                            role="assistant",
                            content=final_text,
                        )
                    )

                    agent_run.intent = (
                        detected_intent
                    )

                    agent_run.latency_ms = round(
                        (
                            time.perf_counter()
                            - run_started
                        )
                        * 1000,
                        2,
                    )

                    agent_run.error = None

                    agent_run.final_response = (
                        final_text
                    )

                    agent_run.trace_json = json.dumps(
                        trace,
                        ensure_ascii=False,
                    )

                    db.commit()

                    return {
                        "response": final_text,
                        "conversation_id": (
                            persisted_conversation_id
                        ),
                        "run_id": run_id,
                        "intent": detected_intent,
                        "resolution": resolution_data,
                        "trace": trace,
                    }

                if not response.candidates:
                    raise RuntimeError(
                        "Gemini requested a tool but "
                        "returned no candidate content."
                    )

                model_content = (
                    response.candidates[0].content
                )

                if model_content is None:
                    raise RuntimeError(
                        "Gemini requested a tool but "
                        "returned empty candidate content."
                    )

                contents.append(
                    model_content
                )

                function_response_parts: list[
                    types.Part
                ] = []

                for function_call in function_calls:
                    tool_name = (
                        function_call.name
                    )

                    arguments = dict(
                        function_call.args
                        or {}
                    )

                    if detected_intent is None:
                        detected_intent = (
                            _intent_from_tool(
                                tool_name
                            )
                        )

                    tool_started = (
                        time.perf_counter()
                    )

                    call_signature = (
                        tool_name
                        + ":"
                        + json.dumps(
                            arguments,
                            sort_keys=True,
                            ensure_ascii=False,
                        )
                    )

                    if call_signature in seen_tool_calls:
                        result = {
                            "status": "ERROR",
                            "error": (
                                "Duplicate tool call blocked."
                            ),
                        }
                    else:
                        seen_tool_calls.add(
                            call_signature
                        )

                        result = _execute_tool(
                            db=db,
                            tool_name=tool_name,
                            arguments=arguments,
                        )

                    tool_latency_ms = round(
                        (
                            time.perf_counter()
                            - tool_started
                        )
                        * 1000,
                        2,
                    )

                    result_status = str(
                        result.get(
                            "status",
                            "ERROR",
                        )
                    )

                    result_error = (
                        result.get(
                            "error"
                        )
                    )

                    db.add(
                        ToolExecution(
                            run_id=run_id,
                            tool_name=tool_name,
                            arguments_json=json.dumps(
                                arguments,
                                ensure_ascii=False,
                            ),
                            result_status=(
                                result_status
                            ),
                            latency_ms=(
                                tool_latency_ms
                            ),
                            result_json=json.dumps(
                                result,
                                ensure_ascii=False,
                            ),
                            error=result_error,
                        )
                    )

                    db.commit()

                    trace.append(
                        {
                            "step": step_number,
                            "type": "tool_call",
                            "tool": tool_name,
                            "arguments": arguments,
                            "result_status": (
                                result_status
                            ),
                            "latency_ms": (
                                tool_latency_ms
                            ),
                            "result": result,
                        }
                    )

                    function_response_parts.append(
                        types.Part.from_function_response(
                            name=tool_name,
                            response={
                                "result": result
                            },
                        )
                    )

                contents.append(
                    types.Content(
                        role="user",
                        parts=(
                            function_response_parts
                        ),
                    )
                )

            from app.agent.resolution import (
                maximum_steps_resolution,
            )

            resolution = (
                maximum_steps_resolution()
            )

            final_text = (
                guard_customer_response(
                    model_response="",
                    resolution=resolution,
                )
            )

            resolution_data = (
                resolution.model_dump(
                    mode="json"
                )
            )

            trace.append(
                {
                    "step": max_steps,
                    "type": "max_steps_reached",
                    "max_steps": max_steps,
                }
            )

            trace.append(
                {
                    "step": max_steps,
                    "type": "resolution",
                    **resolution_data,
                }
            )

            trace.append(
                {
                    "step": max_steps,
                    "type": "final_response",
                    "intent": (
                        detected_intent
                        or "general"
                    ),
                    "response": final_text,
                }
            )

            conversation.resolution_status = (
                resolution.resolution_status
            )

            conversation.current_issue = (
                resolution.issue_type
            )

            db.add(
                Message(
                    conversation_id=(
                        persisted_conversation_id
                    ),
                    role="assistant",
                    content=final_text,
                )
            )

            agent_run.intent = (
                detected_intent
                or "general"
            )

            agent_run.resolution_status = (
                resolution.resolution_status
            )

            agent_run.issue_type = (
                resolution.issue_type
            )

            agent_run.resolution_summary = (
                resolution.summary
            )

            agent_run.final_response = (
                final_text
            )

            agent_run.latency_ms = round(
                (
                    time.perf_counter()
                    - run_started
                )
                * 1000,
                2,
            )

            agent_run.error = None

            agent_run.trace_json = json.dumps(
                trace,
                ensure_ascii=False,
            )

            db.commit()

            return {
                "response": final_text,
                "conversation_id": (
                    persisted_conversation_id
                ),
                "run_id": run_id,
                "intent": (
                    detected_intent
                    or "general"
                ),
                "resolution": (
                    resolution_data
                ),
                "trace": trace,
            }

        except Exception as exc:
            db.rollback()

            failed_run = db.get(
                AgentRun,
                run_id,
            )

            if failed_run is not None:
                failed_run.intent = (
                    detected_intent
                )

                failed_run.latency_ms = round(
                    (
                        time.perf_counter()
                        - run_started
                    )
                    * 1000,
                    2,
                )

                failed_run.error = (
                    f"{type(exc).__name__}: {exc}"
                )

                failed_run.trace_json = json.dumps(
                    trace,
                    ensure_ascii=False,
                )

                db.commit()

            raise