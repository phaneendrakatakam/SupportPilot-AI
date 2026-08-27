import json
import time
from typing import Any

from google import genai
from google.genai import types
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.agent.schemas import (
    CustomerLookupInput,
    KnowledgeSearchInput,
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
from app.db.session import SessionLocal
from app.tools.customer import get_customer
from app.tools.knowledge import search_knowledge_base
from app.tools.service_status import get_service_status
from app.tools.subscription import get_subscription


PROMPT_VERSION = "v1-agent-foundation-3"


SYSTEM_PROMPT = """
You are SupportPilot, the AI customer-support agent for CloudDesk.

Your role is limited to CloudDesk customer support.

Rules:
1. Never invent customer, subscription, service-status, policy, incident,
   account, or support information.
2. Account-specific facts must come from approved tools.
3. Policy and documentation answers must come from search_knowledge_base.
4. If an active customer_id is provided, use that exact ID when an
   account-specific tool requires it.
5. Use get_subscription when the customer asks about their current plan,
   subscription status, requested plan, or subscription state.
6. Use get_customer for customer/account identity or account-status questions.
7. Use get_service_status for outage or service-health questions.
8. Use search_knowledge_base for documented CloudDesk policies and support
   guidance.
9. Do not claim that unsupported actions have been completed.
10. Tool results are the source of truth.
11. If account-specific information is required and no customer_id is
    available, ask the customer for their CloudDesk customer ID. Do not invent
    an ID and do not call an account-specific tool with a made-up value.
12. If a tool reports that a customer, subscription, incident, policy, or
    other record is unavailable or not found, clearly say that the information
    could not be found. Never replace missing information with a guess.
13. If the customer's request is unrelated to CloudDesk products, accounts,
    subscriptions, billing, service availability, policies, or support,
    politely explain that it is outside SupportPilot's support scope.
14. Do not use CloudDesk tools for unrelated questions.
15. Never expose another customer's information.

Knowledge-grounding rules:
16. search_knowledge_base performs semantic retrieval. Its returned passages
    are candidate evidence, not automatic proof that the customer's requested
    fact is true or false.
17. A similarity score only measures semantic closeness. Never treat a high
    score as confirmation that a passage answers the customer's exact question.
18. Before stating a policy, feature, payment method, plan type, limitation,
    eligibility rule, or other documented fact, verify that at least one
    retrieved passage explicitly states or directly supports that claim.
19. Do not infer a negative fact merely because the retrieved passages fail to
    mention something. Missing documentation means the answer is unknown from
    the available knowledge base; it does not mean the feature, policy, or
    option does not exist.
20. If the retrieved passages are related to the general topic but do not
    actually answer the customer's question, say that the available CloudDesk
    documentation does not provide enough information to confirm the answer.
21. For yes/no policy questions, answer yes or no only when the retrieved
    evidence explicitly supports that conclusion. Otherwise use uncertainty
    language such as: "I don't have documented information confirming that."
22. If search_knowledge_base returns NOT_FOUND, NOT_READY, or ERROR, do not
    infer an answer from general knowledge or from the absence of a result.
23. Example: if a customer asks whether CloudDesk offers a lifetime
    subscription and the retrieved passages discuss refunds, billing cycles,
    or upgrades but never mention lifetime subscriptions, do not say that
    CloudDesk does not offer one. Say that the available documentation does not
    confirm whether a lifetime subscription is offered.
24. Example: if a customer asks whether CloudDesk accepts Bitcoin and the
    retrieved passages do not explicitly document cryptocurrency payment
    support, do not claim that CloudDesk accepts or rejects Bitcoin. Say that
    the available documentation does not confirm it.
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


def _execute_tool(
    db: Session,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate Gemini arguments and execute one approved V1 tool.
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
    Convert V1 tool selection into a simple support intent.
    """

    intent_map = {
        "get_customer": "customer_account",
        "get_subscription": "subscription",
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
            raise ValueError(
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


def run_agent(
    message: str,
    customer_id: str | None = None,
    conversation_id: str | None = None,
    max_steps: int = 5,
) -> dict[str, Any]:
    """
    Run the V1 native Gemini tool-calling loop.

    Persists:
    - conversation
    - user message
    - assistant message
    - agent run
    - tool executions
    """

    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured."
        )

    client = genai.Client(
        api_key=settings.gemini_api_key
    )

    active_customer = (
        customer_id
        or "NOT_PROVIDED"
    )

    user_context = (
        f"Active customer_id: {active_customer}\n"
        f"Customer message: {message}"
    )

    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(
                    text=user_context
                )
            ],
        )
    ]

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[V1_TOOL],
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
        )

        db.add(agent_run)

        db.commit()

        persisted_conversation_id = (
            conversation.conversation_id
        )

        run_id = agent_run.run_id

        detected_intent: str | None = None

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

                    db.commit()

                    return {
                        "response": final_text,
                        "conversation_id": (
                            persisted_conversation_id
                        ),
                        "run_id": run_id,
                        "intent": detected_intent,
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

            raise RuntimeError(
                "Agent exceeded the maximum of "
                f"{max_steps} tool/LLM steps."
            )

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

                db.commit()

            raise