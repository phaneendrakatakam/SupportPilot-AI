from __future__ import annotations

import hashlib
import json

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.actions.schemas import (
    ActionRecommendation,
    ApprovalDecisionInput,
    CreateSupportTicketInput,
    RequestRefundReviewInput,
    RetrySubscriptionSyncInput,
)
from app.actions.tools import (
    create_support_ticket,
    request_refund_review,
    retry_subscription_sync,
)
from app.db.models import (
    ActionExecution,
    ActionProposal,
    AgentRun,
    Conversation,
    Customer,
    Payment,
    utcnow,
)


ACTION_INPUT_MODELS = {
    "retry_subscription_sync": RetrySubscriptionSyncInput,
    "create_support_ticket": CreateSupportTicketInput,
    "request_refund_review": RequestRefundReviewInput,
}


REUSABLE_APPROVAL_STATUSES = {
    "PENDING_APPROVAL",
    "APPROVED",
}


def action_business_identity(
    action_name: str,
    arguments: dict,
) -> dict:
    """
    Return the business identity used to decide whether two proposals
    represent the same logical support action.

    Descriptive fields such as refund reason, ticket summary and evidence are
    intentionally excluded so conversational follow-ups cannot create duplicate
    human-review work for the same business object.
    """

    if action_name == "retry_subscription_sync":
        return {
            "customer_id":
                arguments.get("customer_id"),
            "requested_plan":
                arguments.get("requested_plan"),
        }

    if action_name == "request_refund_review":
        return {
            "customer_id":
                arguments.get("customer_id"),
            "payment_id":
                arguments.get("payment_id"),
        }

    if action_name == "create_support_ticket":
        return {
            "customer_id":
                arguments.get("customer_id"),
            "issue_type":
                arguments.get("issue_type"),
        }

    return {
        key: arguments[key]
        for key in sorted(arguments)
    }


def _proposal_arguments(
    proposal: ActionProposal,
) -> dict:
    try:
        value = json.loads(
            proposal.arguments_json
        )
    except (
        TypeError,
        json.JSONDecodeError,
    ):
        return {}

    return (
        value
        if isinstance(value, dict)
        else {}
    )


def _validate_action_resource_ownership(
    db: Session,
    *,
    action_name: str,
    arguments: dict,
    customer_id: str,
) -> None:
    """
    Enforce ownership for action arguments that reference another business
    object directly.

    The most important current case is refund review: payment_id must never
    point at another customer's payment. Missing records are left to the action
    precondition checks so stale proposals can fail safely without being
    reinterpreted as cross-customer access.
    """

    if action_name != "request_refund_review":
        return

    payment_id = arguments.get(
        "payment_id"
    )

    if not payment_id:
        return

    payment = db.get(
        Payment,
        payment_id,
    )

    if (
        payment is not None
        and payment.customer_id
        != customer_id
    ):
        raise ValueError(
            "Refund-review payment does not belong to the proposal customer."
        )


def _validated_execution_arguments(
    db: Session,
    proposal: ActionProposal,
) -> dict:
    """
    Re-validate proposal/customer/conversation/run relationships immediately
    before a controlled write.

    Proposal creation already validates these relationships. Re-checking here
    protects execution against stale data, accidental database edits, corrupted
    proposal payloads, or any future code path that bypasses proposal creation.
    """

    conversation = db.get(
        Conversation,
        proposal.conversation_id,
    )

    if conversation is None:
        raise ValueError(
            "Action proposal conversation no longer exists."
        )

    if (
        conversation.customer_id
        != proposal.customer_id
    ):
        raise ValueError(
            "Action proposal customer no longer matches its conversation."
        )

    agent_run = db.get(
        AgentRun,
        proposal.run_id,
    )

    if agent_run is None:
        raise ValueError(
            "Action proposal agent run no longer exists."
        )

    if (
        agent_run.conversation_id
        != proposal.conversation_id
    ):
        raise ValueError(
            "Action proposal agent run no longer belongs to its conversation."
        )

    customer = db.get(
        Customer,
        proposal.customer_id,
    )

    if customer is None:
        raise ValueError(
            "Action proposal customer no longer exists."
        )

    model_class = ACTION_INPUT_MODELS.get(
        proposal.action_name
    )

    if model_class is None:
        raise ValueError(
            f"Unsupported controlled action: {proposal.action_name}"
        )

    try:
        raw_arguments = json.loads(
            proposal.arguments_json
        )
    except (
        TypeError,
        json.JSONDecodeError,
    ) as exc:
        raise ValueError(
            "Action proposal arguments are not valid JSON."
        ) from exc

    if not isinstance(
        raw_arguments,
        dict,
    ):
        raise ValueError(
            "Action proposal arguments must be an object."
        )

    try:
        validated = model_class(
            **raw_arguments
        ).model_dump(
            mode="json"
        )
    except ValidationError as exc:
        raise ValueError(
            "Action proposal arguments no longer satisfy the action contract."
        ) from exc

    if (
        validated.get(
            "customer_id"
        )
        != proposal.customer_id
    ):
        raise ValueError(
            "Action arguments do not match the proposal customer."
        )

    _validate_action_resource_ownership(
        db,
        action_name=proposal.action_name,
        arguments=validated,
        customer_id=proposal.customer_id,
    )

    return validated


def proposal_equivalence_key(
    proposal: ActionProposal,
) -> str:
    """
    Stable logical key used by the operator queue to collapse old duplicate
    proposals that were created by separate follow-up AgentRuns.
    """

    identity = action_business_identity(
        proposal.action_name,
        _proposal_arguments(
            proposal
        ),
    )

    canonical = json.dumps(
        identity,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return (
        proposal.conversation_id
        + "|"
        + proposal.customer_id
        + "|"
        + proposal.action_name
        + "|"
        + canonical
    )


def find_reusable_action_proposal(
    db: Session,
    *,
    conversation_id: str,
    customer_id: str,
    action_name: str,
    arguments: dict,
) -> ActionProposal | None:
    """
    Reuse a pending/approved equivalent proposal from the same conversation.

    A new AgentRun is created for every customer follow-up, but that must not
    create a second human-review item for the same logical action.
    """

    expected_identity = (
        action_business_identity(
            action_name,
            arguments,
        )
    )

    candidates = list(
        db.scalars(
            select(ActionProposal)
            .where(
                ActionProposal.conversation_id
                == conversation_id,
                ActionProposal.customer_id
                == customer_id,
                ActionProposal.action_name
                == action_name,
                ActionProposal.approval_status.in_(
                    REUSABLE_APPROVAL_STATUSES
                ),
            )
            .order_by(
                ActionProposal.proposed_at.asc(),
                ActionProposal.proposal_id.asc(),
            )
        ).all()
    )

    for candidate in candidates:
        candidate_execution = db.scalar(
            select(ActionExecution).where(
                ActionExecution.proposal_id
                == candidate.proposal_id
            )
        )

        # A terminal failed execution must not permanently poison the logical
        # workflow. A later AgentRun may investigate again and create a fresh
        # proposal if the current evidence still recommends an action.
        if (
            candidate_execution is not None
            and (
                candidate_execution.execution_status
                == "FAILED"
                or candidate_execution.verification_status
                == "FAILED"
            )
        ):
            continue

        candidate_identity = (
            action_business_identity(
                candidate.action_name,
                _proposal_arguments(
                    candidate
                ),
            )
        )

        if (
            candidate_identity
            == expected_identity
        ):
            return candidate

    return None


def _canonical_arguments(
    recommendation: ActionRecommendation,
) -> dict:
    model_class = ACTION_INPUT_MODELS[
        recommendation.action_name
    ]

    validated = model_class(
        **recommendation.arguments
    )

    return validated.model_dump(
        mode="json"
    )


def _idempotency_key(
    run_id: str,
    action_name: str,
    arguments: dict,
) -> str:
    canonical = json.dumps(
        arguments,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    digest = hashlib.sha256(
        (
            run_id
            + "|"
            + action_name
            + "|"
            + canonical
        ).encode("utf-8")
    ).hexdigest()

    return (
        "action:"
        + digest
    )


def create_action_proposal(
    db: Session,
    *,
    conversation_id: str,
    run_id: str,
    customer_id: str,
    recommendation: ActionRecommendation,
) -> ActionProposal:
    """
    Persist one validated V3 action proposal.

    This function does not commit. The caller owns the transaction.
    """

    conversation = db.get(
        Conversation,
        conversation_id,
    )
    agent_run = db.get(
        AgentRun,
        run_id,
    )
    customer = db.get(
        Customer,
        customer_id,
    )

    if conversation is None:
        raise ValueError(
            "Conversation not found for action proposal."
        )

    if agent_run is None:
        raise ValueError(
            "Agent run not found for action proposal."
        )

    if customer is None:
        raise ValueError(
            "Customer not found for action proposal."
        )

    if agent_run.conversation_id != conversation_id:
        raise ValueError(
            "Agent run does not belong to the supplied conversation."
        )

    if conversation.customer_id != customer_id:
        raise ValueError(
            "Customer does not match the supplied conversation."
        )

    arguments = _canonical_arguments(
        recommendation
    )

    action_customer_id = arguments.get(
        "customer_id"
    )

    if action_customer_id != customer_id:
        raise ValueError(
            "Action arguments do not match the proposal customer."
        )

    _validate_action_resource_ownership(
        db,
        action_name=recommendation.action_name,
        arguments=arguments,
        customer_id=customer_id,
    )

    reusable = find_reusable_action_proposal(
        db,
        conversation_id=conversation_id,
        customer_id=customer_id,
        action_name=recommendation.action_name,
        arguments=arguments,
    )

    if reusable is not None:
        return reusable

    key = _idempotency_key(
        run_id=run_id,
        action_name=recommendation.action_name,
        arguments=arguments,
    )

    existing = db.scalar(
        select(ActionProposal).where(
            ActionProposal.idempotency_key
            == key
        )
    )

    if existing is not None:
        return existing

    proposal = ActionProposal(
        conversation_id=conversation_id,
        run_id=run_id,
        customer_id=customer_id,
        action_name=recommendation.action_name,
        arguments_json=json.dumps(
            arguments,
            ensure_ascii=False,
            sort_keys=True,
        ),
        reason=recommendation.reason,
        issue_type=recommendation.issue_type,
        approval_required=True,
        approval_status="PENDING_APPROVAL",
        idempotency_key=key,
    )

    db.add(proposal)
    db.flush()

    return proposal


def _normalized_rejection_reason(
    payload: ApprovalDecisionInput,
) -> str:
    reason = (
        payload.reason
        or "Human operator rejected the proposed controlled action."
    ).strip()

    return (
        reason
        or "Human operator rejected the proposed controlled action."
    )


def _append_human_decision_trace(
    agent_run: AgentRun,
    *,
    proposal: ActionProposal,
    payload: ApprovalDecisionInput,
    fallback_proposal: ActionProposal | None = None,
) -> None:
    """Append an auditable human-decision event to the structured run trace."""

    trace: list[dict] = []

    if agent_run.trace_json:
        try:
            parsed = json.loads(
                agent_run.trace_json
            )
            if isinstance(parsed, list):
                trace = parsed
        except (
            TypeError,
            json.JSONDecodeError,
        ):
            trace = []

    numeric_steps = [
        item.get("step")
        for item in trace
        if (
            isinstance(item, dict)
            and isinstance(item.get("step"), int)
        )
    ]

    next_step = (
        max(numeric_steps) + 1
        if numeric_steps
        else 1
    )

    event = {
        "step": next_step,
        "type": "human_decision",
        "proposal_id": proposal.proposal_id,
        "action_name": proposal.action_name,
        "decision": proposal.approval_status,
        "decided_by": payload.decided_by,
        "reason": _normalized_rejection_reason(
            payload
        ),
    }

    if fallback_proposal is not None:
        event.update(
            {
                "fallback_proposal_id":
                    fallback_proposal.proposal_id,
                "fallback_action_name":
                    fallback_proposal.action_name,
            }
        )

    trace.append(event)

    agent_run.trace_json = json.dumps(
        trace,
        ensure_ascii=False,
    )


def _fallback_ticket_after_rejected_remediation(
    db: Session,
    *,
    proposal: ActionProposal,
    payload: ApprovalDecisionInput,
) -> ActionProposal | None:
    """
    Do not abandon an unresolved subscription case after remediation rejection.

    The rejected write remains blocked. A separate create_support_ticket proposal
    is prepared and still requires its own human approval and execution.
    """

    if proposal.action_name != "retry_subscription_sync":
        return None

    arguments = _proposal_arguments(
        proposal
    )
    requested_plan = (
        arguments.get("requested_plan")
        or "UNKNOWN"
    )
    rejection_reason = (
        _normalized_rejection_reason(
            payload
        )
    )

    recommendation = ActionRecommendation(
        action_name="create_support_ticket",
        arguments={
            "customer_id": proposal.customer_id,
            "issue_type": "subscription_remediation_rejected",
            "summary": (
                "The proposed subscription synchronization retry was rejected "
                "by a human operator. No account change was made. The original "
                "subscription issue remains unresolved and requires specialist "
                "investigation before any further remediation."
            ),
            "priority": "HIGH",
            "evidence": [
                f"Original issue type: {proposal.issue_type}.",
                "Rejected controlled action: retry_subscription_sync.",
                f"Requested subscription plan: {requested_plan}.",
                f"Original recommendation: {proposal.reason}",
                f"Human rejection reason: {rejection_reason}",
                (
                    "No account change was made because the rejected "
                    "remediation was not executed."
                ),
            ],
        },
        reason=(
            "The human operator rejected the proposed subscription remediation "
            f"({rejection_reason}). The customer issue remains unresolved, so "
            "SupportPilot is preparing a separate specialist support-ticket "
            "proposal."
        ),
        issue_type="subscription_remediation_rejected",
    )

    return create_action_proposal(
        db,
        conversation_id=proposal.conversation_id,
        run_id=proposal.run_id,
        customer_id=proposal.customer_id,
        recommendation=recommendation,
    )


def approve_action(
    db: Session,
    proposal_id: str,
    payload: ApprovalDecisionInput,
) -> ActionProposal:
    """
    Record explicit human approval.

    This function does not commit. The caller owns the transaction.
    """

    proposal = db.get(
        ActionProposal,
        proposal_id,
    )

    if proposal is None:
        raise ValueError(
            "Action proposal not found."
        )

    if proposal.approval_status == "REJECTED":
        raise ValueError(
            "A rejected action proposal cannot be approved."
        )

    if proposal.approval_status == "APPROVED":
        return proposal

    if proposal.approval_status != "PENDING_APPROVAL":
        raise ValueError(
            "Action proposal is not awaiting approval."
        )

    proposal.approval_status = "APPROVED"
    proposal.decided_by = payload.decided_by
    proposal.decided_at = utcnow()

    db.flush()

    return proposal


def reject_action(
    db: Session,
    proposal_id: str,
    payload: ApprovalDecisionInput,
) -> ActionProposal:
    """
    Record explicit human rejection without executing the rejected action.

    Rejected subscription remediation also prepares a separate specialist-ticket
    proposal. That fallback proposal is not approved or executed automatically.
    """

    proposal = db.get(
        ActionProposal,
        proposal_id,
    )

    if proposal is None:
        raise ValueError(
            "Action proposal not found."
        )

    if proposal.approval_status == "APPROVED":
        raise ValueError(
            "An approved action proposal cannot be rejected."
        )

    if proposal.approval_status == "REJECTED":
        return proposal

    if proposal.approval_status != "PENDING_APPROVAL":
        raise ValueError(
            "Action proposal is not awaiting approval."
        )

    proposal.approval_status = "REJECTED"
    proposal.decided_by = payload.decided_by
    proposal.decided_at = utcnow()

    fallback_proposal = (
        _fallback_ticket_after_rejected_remediation(
            db,
            proposal=proposal,
            payload=payload,
        )
    )

    agent_run = db.get(
        AgentRun,
        proposal.run_id,
    )

    if agent_run is not None:
        _append_human_decision_trace(
            agent_run,
            proposal=proposal,
            payload=payload,
            fallback_proposal=fallback_proposal,
        )

    db.flush()

    return proposal


def execute_approved_action(
    db: Session,
    proposal_id: str,
) -> ActionExecution:
    """
    Execute one explicitly approved controlled action.

    This function never approves an action and never commits. The caller owns
    both human-approval collection and the surrounding database transaction.
    """

    # Lock the proposal row for the lifetime of this transaction.
    #
    # Sequential duplicate requests were already idempotent because an existing
    # ActionExecution is returned below. The row lock also closes the race where
    # two operator/browser requests arrive at nearly the same time, both observe
    # "no execution yet", and both attempt the controlled action.
    #
    # PostgreSQL serializes the requests on this proposal. After the first
    # transaction commits, the second request continues and reuses the persisted
    # ActionExecution instead of executing the business action again.
    proposal = db.scalar(
        select(ActionProposal)
        .where(
            ActionProposal.proposal_id
            == proposal_id
        )
        .with_for_update()
    )

    if proposal is None:
        raise ValueError(
            "Action proposal not found."
        )

    if proposal.approval_status != "APPROVED":
        raise PermissionError(
            "Action execution requires explicit human approval."
        )

    arguments = _validated_execution_arguments(
        db,
        proposal,
    )

    existing = db.scalar(
        select(ActionExecution).where(
            ActionExecution.proposal_id
            == proposal_id
        )
    )

    if existing is not None:
        return existing

    execution = ActionExecution(
        proposal_id=proposal_id,
        execution_status="EXECUTING",
        verification_status="PENDING",
        started_at=utcnow(),
    )

    db.add(execution)
    db.flush()

    action_savepoint = db.begin_nested()

    try:
        if proposal.action_name == "retry_subscription_sync":
            action_result = retry_subscription_sync(
                db,
                RetrySubscriptionSyncInput(
                    **arguments
                ),
            )

        elif proposal.action_name == "create_support_ticket":
            action_result = create_support_ticket(
                db,
                CreateSupportTicketInput(
                    **arguments
                ),
                conversation_id=proposal.conversation_id,
                run_id=proposal.run_id,
                proposal_id=proposal.proposal_id,
            )

        elif proposal.action_name == "request_refund_review":
            action_result = request_refund_review(
                db,
                RequestRefundReviewInput(
                    **arguments
                ),
                conversation_id=proposal.conversation_id,
                run_id=proposal.run_id,
                proposal_id=proposal.proposal_id,
            )

        else:
            raise ValueError(
                f"Unsupported controlled action: {proposal.action_name}"
            )

        verification_passed = (
            action_result.verification_status
            == "VERIFIED"
        )

        if verification_passed:
            action_savepoint.commit()
        else:
            # Never leave an unverified state-changing write in the outer
            # transaction. The attempted result is still recorded below for
            # operator/debug auditability.
            action_savepoint.rollback()

        if verification_passed:
            recorded_execution_status = (
                action_result.execution_status
            )
            recorded_verification_status = (
                "VERIFIED"
            )
        else:
            recorded_execution_status = (
                "SKIPPED"
                if action_result.execution_status
                == "SKIPPED"
                else "FAILED"
            )
            recorded_verification_status = (
                "FAILED"
            )

        result_payload = dict(
            action_result.result
        )
        result_payload[
            "business_write_committed"
        ] = (
            verification_passed
            and action_result.execution_status
            == "SUCCEEDED"
        )

        if not verification_passed:
            result_payload[
                "safe_rollback_applied"
            ] = True

            if (
                action_result.execution_status
                == "SUCCEEDED"
            ):
                result_payload[
                    "attempted_execution_status"
                ] = "SUCCEEDED"

        execution.execution_status = (
            recorded_execution_status
        )
        execution.verification_status = (
            recorded_verification_status
        )
        execution.before_state_json = (
            json.dumps(
                action_result.before_state,
                ensure_ascii=False,
            )
            if action_result.before_state
            is not None
            else None
        )
        execution.result_json = json.dumps(
            result_payload,
            ensure_ascii=False,
        )
        execution.after_state_json = (
            json.dumps(
                action_result.after_state,
                ensure_ascii=False,
            )
            if action_result.after_state
            is not None
            else None
        )
        execution.verification_result_json = (
            json.dumps(
                action_result.verification_result,
                ensure_ascii=False,
            )
            if action_result.verification_result
            is not None
            else None
        )
        execution.error = action_result.error
        execution.completed_at = utcnow()
        execution.verified_at = utcnow()

        if (
            not verification_passed
            and not execution.error
        ):
            execution.error = (
                "Controlled action did not pass post-action verification."
            )

        db.flush()

        return execution

    except Exception as exc:
        # This catches unexpected action-layer failures while intentionally
        # leaving pre-execution authorization/context validation outside this
        # block. The SAVEPOINT ensures any partial business mutation from the
        # action attempt is reverted while this ActionExecution can still be
        # persisted by the outer transaction.
        if action_savepoint.is_active:
            action_savepoint.rollback()

        execution.execution_status = "FAILED"
        execution.verification_status = "FAILED"
        execution.result_json = json.dumps(
            {
                "reason": (
                    "The controlled action failed before a verified business "
                    "change could be committed."
                ),
                "business_write_committed": False,
                "safe_rollback_applied": True,
                "exception_type": type(exc).__name__,
            },
            ensure_ascii=False,
        )
        execution.error = (
            f"{type(exc).__name__}: {exc}"
        )
        execution.completed_at = utcnow()
        execution.verified_at = utcnow()

        db.flush()

        return execution
