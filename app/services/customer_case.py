from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.actions.service import proposal_equivalence_key
from app.db.models import (
    ActionExecution,
    ActionProposal,
    Conversation,
    Message,
    RefundReview,
    SupportTicket,
)


CASE_TYPE_BY_ACTION = {
    "retry_subscription_sync": "SUBSCRIPTION_UPDATE",
    "create_support_ticket": "SUPPORT_CASE",
    "request_refund_review": "REFUND_REVIEW",
}


def _safe_json_load(
    value: str | None,
    fallback: Any,
) -> Any:
    if not value:
        return fallback

    try:
        return json.loads(
            value
        )
    except (
        TypeError,
        json.JSONDecodeError,
    ):
        return fallback


def _lifecycle_rank(
    proposal: ActionProposal,
    execution: ActionExecution | None,
) -> int:
    """
    Rank one proposal by how far its controlled workflow progressed.

    This mirrors the Human Review Queue rule so customer case status and
    operator status cannot disagree when legacy duplicate proposals exist.
    """

    if (
        execution is not None
        and execution.verification_status
        == "VERIFIED"
    ):
        return 60

    if (
        execution is not None
        and execution.verification_status
        == "FAILED"
    ):
        return 55

    if (
        execution is not None
        and execution.execution_status
        == "SUCCEEDED"
    ):
        return 50

    if (
        execution is not None
        and execution.execution_status
        == "FAILED"
    ):
        return 45

    if proposal.approval_status == "APPROVED":
        return 40

    if proposal.approval_status == "PENDING_APPROVAL":
        return 30

    if proposal.approval_status == "REJECTED":
        return 10

    return 0


def _prefer_proposal(
    current: ActionProposal,
    current_execution: ActionExecution | None,
    candidate: ActionProposal,
    candidate_execution: ActionExecution | None,
) -> bool:
    """Return True when candidate is the better logical representative."""

    current_rank = _lifecycle_rank(
        current,
        current_execution,
    )
    candidate_rank = _lifecycle_rank(
        candidate,
        candidate_execution,
    )

    if candidate_rank != current_rank:
        return candidate_rank > current_rank

    return (
        candidate.proposed_at
        < current.proposed_at
    )


def latest_action_context(
    db: Session,
    conversation_id: str,
) -> tuple[
    ActionProposal | None,
    ActionExecution | None,
]:
    """
    Return the latest logical workflow using its most-progressed proposal.

    Older versions selected the newest raw ActionProposal. A historical
    duplicate PENDING_APPROVAL row could therefore hide an already VERIFIED
    proposal for the same refund/payment or subscription action.

    The resolver now groups equivalent proposals, keeps the most-progressed
    representative inside each group, then chooses the newest logical workflow.
    """

    proposals = list(
        db.scalars(
            select(ActionProposal)
            .where(
                ActionProposal.conversation_id
                == conversation_id
            )
            .order_by(
                ActionProposal.proposed_at.desc(),
                ActionProposal.proposal_id.desc(),
            )
        ).all()
    )

    if not proposals:
        return None, None

    proposal_ids = [
        proposal.proposal_id
        for proposal in proposals
    ]

    executions = list(
        db.scalars(
            select(ActionExecution).where(
                ActionExecution.proposal_id.in_(
                    proposal_ids
                )
            )
        ).all()
    )

    executions_by_proposal = {
        execution.proposal_id:
            execution
        for execution in executions
    }

    groups: dict[str, dict[str, Any]] = {}

    for proposal in proposals:
        key = proposal_equivalence_key(
            proposal
        )

        execution = executions_by_proposal.get(
            proposal.proposal_id
        )

        group = groups.get(
            key
        )

        if group is None:
            groups[key] = {
                "latest_proposed_at":
                    proposal.proposed_at,
                "latest_proposal_id":
                    proposal.proposal_id,
                "proposal":
                    proposal,
                "execution":
                    execution,
            }
            continue

        if (
            proposal.proposed_at
            > group["latest_proposed_at"]
        ):
            group["latest_proposed_at"] = (
                proposal.proposed_at
            )
            group["latest_proposal_id"] = (
                proposal.proposal_id
            )

        current = group["proposal"]
        current_execution = group["execution"]

        if _prefer_proposal(
            current,
            current_execution,
            proposal,
            execution,
        ):
            group["proposal"] = proposal
            group["execution"] = execution

    selected_group = max(
        groups.values(),
        key=lambda item: (
            item["latest_proposed_at"],
            item["latest_proposal_id"],
        ),
    )

    return (
        selected_group["proposal"],
        selected_group["execution"],
    )


def _base_snapshot(
    conversation: Conversation,
) -> dict[str, Any]:
    return {
        "conversation_id":
            conversation.conversation_id,
        "customer_id":
            conversation.customer_id,
        "case_status":
            "NO_ACTIVE_CASE",
        "case_type":
            None,
        "title":
            "No active case",
        "message":
            "Ask a support question to get started.",
        "current_plan":
            None,
        "reference":
            None,
        "customer_message":
            None,
        "updated_at":
            conversation.created_at,
    }


def build_customer_case_snapshot(
    db: Session,
    conversation: Conversation,
    proposal: ActionProposal | None = None,
    execution: ActionExecution | None = None,
) -> dict[str, Any]:
    """
    Build a customer-safe representation of the latest support case.

    Internal action names, proposal IDs, execution IDs, raw payloads,
    approval metadata, and operator details are intentionally excluded.
    """

    snapshot = _base_snapshot(
        conversation
    )

    if proposal is None:
        proposal, execution = latest_action_context(
            db,
            conversation.conversation_id,
        )

    if proposal is None:
        if (
            conversation.resolution_status
            == "ESCALATION_REQUIRED"
        ):
            snapshot.update(
                {
                    "case_status":
                        "UNDER_REVIEW",
                    "case_type":
                        "GENERAL_REVIEW",
                    "title":
                        "Additional support review needed",
                    "message": (
                        "SupportPilot completed the available checks, "
                        "but this issue needs additional support review."
                    ),
                }
            )

        elif (
            conversation.resolution_status
            == "NEEDS_INFORMATION"
        ):
            snapshot.update(
                {
                    "case_status":
                        "NEEDS_INFORMATION",
                    "case_type":
                        "GENERAL_REVIEW",
                    "title":
                        "We need a little more information",
                    "message": (
                        "Continue the conversation so SupportPilot can "
                        "complete the review."
                    ),
                }
            )

        elif (
            conversation.resolution_status
            == "UNRESOLVED"
        ):
            snapshot.update(
                {
                    "case_status":
                        "NEEDS_SUPPORT",
                    "case_type":
                        "GENERAL_REVIEW",
                    "title":
                        "We still need to review this",
                    "message": (
                        "The issue is not resolved yet and still needs "
                        "support review."
                    ),
                }
            )

        return snapshot

    case_type = CASE_TYPE_BY_ACTION.get(
        proposal.action_name,
        "GENERAL_REVIEW",
    )

    snapshot.update(
        {
            "case_status":
                "UNDER_REVIEW",
            "case_type":
                case_type,
            "title":
                "We found the issue",
            "message": (
                "We found the issue and it is being safely reviewed."
            ),
            "updated_at":
                (
                    proposal.decided_at
                    or proposal.proposed_at
                ),
        }
    )

    if case_type == "SUBSCRIPTION_UPDATE":
        snapshot["message"] = (
            "Your payment went through, but the requested plan update "
            "has not been applied yet. You do not need to pay again."
        )

    elif case_type == "SUPPORT_CASE":
        if (
            proposal.issue_type
            == "subscription_remediation_rejected"
        ):
            snapshot.update(
                {
                    "title": (
                        "Your case is being prepared for specialist review"
                    ),
                    "message": (
                        "The proposed fix was not approved, so no account "
                        "changes were made. A specialist support case is now "
                        "waiting for human approval."
                    ),
                    "customer_message": (
                        "The proposed fix was not approved, so no account "
                        "changes were made. Your issue is now being prepared "
                        "for specialist support review."
                    ),
                }
            )
        else:
            snapshot["message"] = (
                "This issue needs a human support case. "
                "No unsupported account change has been made."
            )

    elif case_type == "REFUND_REVIEW":
        snapshot["message"] = (
            "Your payment was verified and the refund request needs "
            "human review. No refund has been issued automatically."
        )

    if proposal.approval_status == "REJECTED":
        snapshot.update(
            {
                "case_status":
                    "NEEDS_SUPPORT",
                "title":
                    "Your case still needs support",
                "message": (
                    "The proposed support step was not approved. "
                    "No account change was made."
                ),
                "customer_message": (
                    "The proposed support step was not approved. "
                    "No account change was made, and your issue still "
                    "needs support review."
                ),
            }
        )
        return snapshot

    if execution is None:
        return snapshot

    snapshot["updated_at"] = (
        execution.verified_at
        or execution.completed_at
        or execution.started_at
        or execution.created_at
    )

    if (
        execution.execution_status
        == "FAILED"
        or execution.verification_status
        == "FAILED"
    ):
        snapshot.update(
            {
                "case_status":
                    "NEEDS_SUPPORT",
                "title":
                    "We still need to review this",
                "message": (
                    "The recommended support step could not be completed "
                    "safely. The issue still needs support review."
                ),
                "customer_message": (
                    "We couldn't safely complete the recommended support "
                    "step. No unsupported account change was made, and "
                    "your issue still needs support review."
                ),
            }
        )
        return snapshot

    if execution.verification_status != "VERIFIED":
        return snapshot

    after_state = _safe_json_load(
        execution.after_state_json,
        {},
    )
    result = _safe_json_load(
        execution.result_json,
        {},
    )
    arguments = _safe_json_load(
        proposal.arguments_json,
        {},
    )

    if case_type == "SUBSCRIPTION_UPDATE":
        requested_plan = (
            arguments.get("requested_plan")
            or after_state.get("requested_plan")
        )
        current_plan = after_state.get(
            "plan"
        )
        sync_status = after_state.get(
            "last_sync_status"
        )

        if (
            current_plan
            and requested_plan
            and current_plan == requested_plan
            and sync_status == "SUCCESS"
        ):
            customer_message = (
                f"Your account has now been updated to **{current_plan}**. "
                "I re-checked the subscription and confirmed the update "
                "completed successfully."
            )

            snapshot.update(
                {
                    "case_status":
                        "RESOLVED",
                    "title":
                        "Your issue is resolved",
                    "message": (
                        f"Your account is now on {current_plan} and the "
                        "subscription update was verified successfully."
                    ),
                    "current_plan":
                        current_plan,
                    "customer_message":
                        customer_message,
                }
            )
            return snapshot

        snapshot.update(
            {
                "case_status":
                    "NEEDS_SUPPORT",
                "title":
                    "We still need to review this",
                "message": (
                    "The subscription update ran, but the final account "
                    "state could not be verified."
                ),
            }
        )
        return snapshot

    if case_type == "SUPPORT_CASE":
        ticket = db.scalar(
            select(SupportTicket).where(
                SupportTicket.proposal_id
                == proposal.proposal_id
            )
        )

        ticket_number = (
            ticket.ticket_number
            if ticket is not None
            else (
                result.get("ticket_number")
                or after_state.get("ticket_number")
            )
        )

        if ticket_number:
            customer_message = (
                "Your issue has been escalated to our support team. "
                f"Your case reference is **{ticket_number}**. "
                "The case is now open for human follow-up."
            )

            snapshot.update(
                {
                    "case_status":
                        "CASE_OPEN",
                    "title":
                        "Your case has been escalated",
                    "message": (
                        "A support case was created for human follow-up. "
                        f"Your case reference is {ticket_number}."
                    ),
                    "reference":
                        ticket_number,
                    "customer_message":
                        customer_message,
                }
            )
            return snapshot

    if case_type == "REFUND_REVIEW":
        review = db.scalar(
            select(RefundReview).where(
                RefundReview.proposal_id
                == proposal.proposal_id
            )
        )

        review_number = (
            review.review_number
            if review is not None
            else (
                result.get("review_number")
                or after_state.get("review_number")
            )
        )

        if review_number:
            customer_message = (
                "Your refund request has been submitted for human review. "
                f"Your review reference is **{review_number}**. "
                "No refund was issued automatically."
            )

            snapshot.update(
                {
                    "case_status":
                        "REFUND_REVIEW_OPEN",
                    "title":
                        "Your refund review was submitted",
                    "message": (
                        "Your refund request is now waiting for human review. "
                        f"Your review reference is {review_number}. "
                        "No refund was issued automatically."
                    ),
                    "reference":
                        review_number,
                    "customer_message":
                        customer_message,
                }
            )
            return snapshot

    snapshot.update(
        {
            "case_status":
                "NEEDS_SUPPORT",
            "title":
                "We still need to review this",
            "message": (
                "The support step completed, but the customer outcome "
                "could not be verified safely."
            ),
        }
    )
    return snapshot


def persist_verified_customer_outcome(
    db: Session,
    proposal: ActionProposal,
    execution: ActionExecution,
) -> dict[str, Any]:
    """
    Persist the customer-facing outcome after a verified controlled action.

    The helper is idempotent: repeated execution requests do not create
    duplicate assistant messages.
    """

    conversation = db.get(
        Conversation,
        proposal.conversation_id,
    )

    if conversation is None:
        raise ValueError(
            "Conversation not found for customer outcome."
        )

    snapshot = build_customer_case_snapshot(
        db,
        conversation,
        proposal,
        execution,
    )

    if execution.verification_status != "VERIFIED":
        return snapshot

    if snapshot["case_status"] == "RESOLVED":
        conversation.resolution_status = (
            "RESOLVED"
        )

    elif snapshot["case_status"] in {
        "CASE_OPEN",
        "REFUND_REVIEW_OPEN",
    }:
        conversation.resolution_status = (
            "ESCALATION_REQUIRED"
        )

    customer_message = snapshot.get(
        "customer_message"
    )

    if customer_message:
        existing_message = db.scalar(
            select(Message).where(
                Message.conversation_id
                == conversation.conversation_id,
                Message.role
                == "assistant",
                Message.content
                == customer_message,
            )
        )

        if existing_message is None:
            db.add(
                Message(
                    conversation_id=(
                        conversation.conversation_id
                    ),
                    role="assistant",
                    content=customer_message,
                )
            )

    db.flush()

    return snapshot
