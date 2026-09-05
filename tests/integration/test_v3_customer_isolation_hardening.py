import json

import pytest
from sqlalchemy import select

from app.actions.schemas import (
    ActionRecommendation,
    ApprovalDecisionInput,
)
from app.actions.service import (
    approve_action,
    create_action_proposal,
    execute_approved_action,
)
from app.db.models import (
    ActionExecution,
    AgentRun,
    Conversation,
    Payment,
    RefundReview,
    Subscription,
)
from app.db.session import SessionLocal


def _context(
    db,
    customer_id: str,
    *,
    issue_type: str = "subscription_upgrade_failure",
):
    conversation = Conversation(
        customer_id=customer_id,
        current_issue=issue_type,
        resolution_status="ESCALATION_REQUIRED",
    )
    db.add(
        conversation
    )
    db.flush()

    run = AgentRun(
        conversation_id=conversation.conversation_id,
        resolution_status="ESCALATION_REQUIRED",
        issue_type=issue_type,
        resolution_summary="Customer isolation hardening test.",
    )
    db.add(
        run
    )
    db.flush()

    return conversation, run


def _retry_recommendation() -> ActionRecommendation:
    return ActionRecommendation(
        action_name="retry_subscription_sync",
        arguments={
            "customer_id": "CUS-1007",
            "requested_plan": "PRO",
        },
        reason=(
            "Successful Pro payment with failed subscription synchronization."
        ),
        issue_type="subscription_upgrade_failure",
    )


def _refund_recommendation(
    *,
    payment_id: str = "PAY-3002",
) -> ActionRecommendation:
    return ActionRecommendation(
        action_name="request_refund_review",
        arguments={
            "customer_id": "CUS-1002",
            "payment_id": payment_id,
            "reason": "Customer explicitly requested a refund review.",
        },
        reason=(
            "Verified payment requires a controlled human refund-review request."
        ),
        issue_type="refund_request",
    )


def _approve(
    db,
    proposal_id: str,
) -> None:
    approve_action(
        db,
        proposal_id,
        ApprovalDecisionInput(
            decided_by="support-operator"
        ),
    )


def test_execution_blocks_tampered_cross_customer_action_arguments() -> None:
    with SessionLocal() as db:
        conversation, run = _context(
            db,
            "CUS-1007",
        )

        proposal = create_action_proposal(
            db,
            conversation_id=conversation.conversation_id,
            run_id=run.run_id,
            customer_id="CUS-1007",
            recommendation=_retry_recommendation(),
        )

        _approve(
            db,
            proposal.proposal_id,
        )

        proposal.arguments_json = json.dumps(
            {
                "customer_id": "CUS-1002",
                "requested_plan": "PRO",
            }
        )
        db.flush()

        with pytest.raises(
            ValueError,
            match="Action arguments do not match",
        ):
            execute_approved_action(
                db,
                proposal.proposal_id,
            )

        execution = db.scalar(
            select(ActionExecution).where(
                ActionExecution.proposal_id
                == proposal.proposal_id
            )
        )
        subscription = db.scalar(
            select(Subscription).where(
                Subscription.customer_id
                == "CUS-1007"
            )
        )

        assert execution is None
        assert subscription is not None
        assert subscription.plan == "BASIC"
        assert (
            subscription.last_sync_status
            == "FAILED"
        )

        db.rollback()


def test_execution_blocks_proposal_when_conversation_customer_drifted() -> None:
    with SessionLocal() as db:
        conversation, run = _context(
            db,
            "CUS-1007",
        )

        proposal = create_action_proposal(
            db,
            conversation_id=conversation.conversation_id,
            run_id=run.run_id,
            customer_id="CUS-1007",
            recommendation=_retry_recommendation(),
        )

        _approve(
            db,
            proposal.proposal_id,
        )

        conversation.customer_id = "CUS-1002"
        db.flush()

        with pytest.raises(
            ValueError,
            match="no longer matches its conversation",
        ):
            execute_approved_action(
                db,
                proposal.proposal_id,
            )

        execution = db.scalar(
            select(ActionExecution).where(
                ActionExecution.proposal_id
                == proposal.proposal_id
            )
        )

        assert execution is None

        db.rollback()


def test_execution_blocks_proposal_when_agent_run_moves_to_other_conversation() -> None:
    with SessionLocal() as db:
        conversation, run = _context(
            db,
            "CUS-1007",
        )

        proposal = create_action_proposal(
            db,
            conversation_id=conversation.conversation_id,
            run_id=run.run_id,
            customer_id="CUS-1007",
            recommendation=_retry_recommendation(),
        )

        _approve(
            db,
            proposal.proposal_id,
        )

        other_conversation = Conversation(
            customer_id="CUS-1007",
            resolution_status="ESCALATION_REQUIRED",
        )
        db.add(
            other_conversation
        )
        db.flush()

        run.conversation_id = (
            other_conversation.conversation_id
        )
        db.flush()

        with pytest.raises(
            ValueError,
            match="agent run no longer belongs",
        ):
            execute_approved_action(
                db,
                proposal.proposal_id,
            )

        execution = db.scalar(
            select(ActionExecution).where(
                ActionExecution.proposal_id
                == proposal.proposal_id
            )
        )

        assert execution is None

        db.rollback()


def test_refund_proposal_rejects_payment_owned_by_another_customer() -> None:
    with SessionLocal() as db:
        conversation, run = _context(
            db,
            "CUS-1002",
            issue_type="refund_request",
        )

        # PAY-3007 belongs to CUS-1007, while this conversation is CUS-1002.
        with pytest.raises(
            ValueError,
            match="payment does not belong",
        ):
            create_action_proposal(
                db,
                conversation_id=conversation.conversation_id,
                run_id=run.run_id,
                customer_id="CUS-1002",
                recommendation=_refund_recommendation(
                    payment_id="PAY-3007",
                ),
            )

        db.rollback()


def test_refund_execution_rechecks_payment_ownership_after_approval() -> None:
    with SessionLocal() as db:
        conversation, run = _context(
            db,
            "CUS-1002",
            issue_type="refund_request",
        )

        proposal = create_action_proposal(
            db,
            conversation_id=conversation.conversation_id,
            run_id=run.run_id,
            customer_id="CUS-1002",
            recommendation=_refund_recommendation(),
        )

        _approve(
            db,
            proposal.proposal_id,
        )

        payment = db.get(
            Payment,
            "PAY-3002",
        )

        assert payment is not None
        assert payment.customer_id == "CUS-1002"

        # Simulate stale/corrupted ownership after the human approved the
        # proposal. The execution boundary must re-check ownership.
        payment.customer_id = "CUS-1007"
        db.flush()

        with pytest.raises(
            ValueError,
            match="payment does not belong",
        ):
            execute_approved_action(
                db,
                proposal.proposal_id,
            )

        execution = db.scalar(
            select(ActionExecution).where(
                ActionExecution.proposal_id
                == proposal.proposal_id
            )
        )
        review = db.scalar(
            select(RefundReview).where(
                RefundReview.proposal_id
                == proposal.proposal_id
            )
        )

        assert execution is None
        assert review is None
        assert payment.status == "SUCCESS"

        db.rollback()
