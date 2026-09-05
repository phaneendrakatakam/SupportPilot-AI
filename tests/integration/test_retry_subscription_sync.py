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
    AgentRun,
    Conversation,
    Subscription,
)
from app.db.session import SessionLocal


def build_retry_proposal(db):
    conversation = Conversation(
        customer_id="CUS-1007"
    )
    db.add(conversation)
    db.flush()

    run = AgentRun(
        conversation_id=conversation.conversation_id,
        resolution_status="ESCALATION_REQUIRED",
        issue_type="subscription_upgrade_failure",
        resolution_summary="Paid Pro upgrade was not applied.",
    )
    db.add(run)
    db.flush()

    proposal = create_action_proposal(
        db,
        conversation_id=conversation.conversation_id,
        run_id=run.run_id,
        customer_id="CUS-1007",
        recommendation=ActionRecommendation(
            action_name="retry_subscription_sync",
            arguments={
                "customer_id": "CUS-1007",
                "requested_plan": "PRO",
            },
            reason=(
                "Successful Pro payment with failed subscription synchronization."
            ),
            issue_type="subscription_upgrade_failure",
        ),
    )

    return proposal


def test_retry_cannot_execute_without_human_approval() -> None:
    with SessionLocal() as db:
        proposal = build_retry_proposal(db)

        with pytest.raises(PermissionError):
            execute_approved_action(
                db,
                proposal.proposal_id,
            )

        db.rollback()


def test_approved_retry_executes_and_verifies_subscription() -> None:
    with SessionLocal() as db:
        proposal = build_retry_proposal(db)

        approve_action(
            db,
            proposal.proposal_id,
            ApprovalDecisionInput(
                decided_by="support-operator"
            ),
        )

        execution = execute_approved_action(
            db,
            proposal.proposal_id,
        )

        assert execution.execution_status == "SUCCEEDED"
        assert execution.verification_status == "VERIFIED"

        before = json.loads(
            execution.before_state_json
        )
        after = json.loads(
            execution.after_state_json
        )

        assert before["plan"] == "BASIC"
        assert before["last_sync_status"] == "FAILED"
        assert after["plan"] == "PRO"
        assert after["last_sync_status"] == "SUCCESS"

        subscription = db.scalar(
            select(Subscription).where(
                Subscription.customer_id
                == "CUS-1007"
            )
        )

        assert subscription.plan == "PRO"
        assert subscription.last_sync_status == "SUCCESS"

        duplicate = execute_approved_action(
            db,
            proposal.proposal_id,
        )

        assert duplicate.execution_id == execution.execution_id

        db.rollback()


def test_stale_retry_is_skipped_when_issue_was_already_fixed() -> None:
    with SessionLocal() as db:
        proposal = build_retry_proposal(db)

        subscription = db.scalar(
            select(Subscription).where(
                Subscription.customer_id
                == "CUS-1007"
            )
        )

        subscription.plan = "PRO"
        subscription.last_sync_status = "SUCCESS"
        db.flush()

        approve_action(
            db,
            proposal.proposal_id,
            ApprovalDecisionInput(
                decided_by="support-operator"
            ),
        )

        execution = execute_approved_action(
            db,
            proposal.proposal_id,
        )

        assert execution.execution_status == "SKIPPED"
        assert execution.verification_status == "VERIFIED"

        result = json.loads(
            execution.result_json
        )

        assert "stale" in result["reason"].lower()

        db.rollback()
