import json

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.actions.schemas import (
    ActionRecommendation,
    ApprovalDecisionInput,
)
from app.actions.service import (
    approve_action,
    create_action_proposal,
    execute_approved_action,
    reject_action,
)
from app.db.models import (
    ActionProposal,
    AgentRun,
    Conversation,
)
from app.db.session import SessionLocal


def build_context(db, customer_id: str = "CUS-1007"):
    conversation = Conversation(
        customer_id=customer_id
    )
    db.add(conversation)
    db.flush()

    run = AgentRun(
        conversation_id=conversation.conversation_id,
        resolution_status="ESCALATION_REQUIRED",
        issue_type="subscription_upgrade_failure",
        resolution_summary="Paid upgrade was not applied.",
    )
    db.add(run)
    db.flush()

    return conversation, run


def retry_recommendation() -> ActionRecommendation:
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


def test_action_proposal_persistence_is_idempotent() -> None:
    with SessionLocal() as db:
        conversation, run = build_context(db)

        first = create_action_proposal(
            db,
            conversation_id=conversation.conversation_id,
            run_id=run.run_id,
            customer_id="CUS-1007",
            recommendation=retry_recommendation(),
        )

        second = create_action_proposal(
            db,
            conversation_id=conversation.conversation_id,
            run_id=run.run_id,
            customer_id="CUS-1007",
            recommendation=retry_recommendation(),
        )

        assert first.proposal_id == second.proposal_id
        assert first.approval_status == "PENDING_APPROVAL"
        assert json.loads(first.arguments_json)["requested_plan"] == "PRO"

        db.rollback()


def test_action_proposal_rejects_cross_customer_context() -> None:
    with SessionLocal() as db:
        conversation, run = build_context(
            db,
            customer_id="CUS-1002",
        )

        with pytest.raises(ValueError):
            create_action_proposal(
                db,
                conversation_id=conversation.conversation_id,
                run_id=run.run_id,
                customer_id="CUS-1007",
                recommendation=retry_recommendation(),
            )

        db.rollback()


def test_action_proposal_validates_action_arguments() -> None:
    with SessionLocal() as db:
        conversation, run = build_context(db)

        invalid = ActionRecommendation(
            action_name="retry_subscription_sync",
            arguments={
                "customer_id": "CUS-1007",
            },
            reason="Missing requested plan.",
            issue_type="subscription_upgrade_failure",
        )

        with pytest.raises(ValidationError):
            create_action_proposal(
                db,
                conversation_id=conversation.conversation_id,
                run_id=run.run_id,
                customer_id="CUS-1007",
                recommendation=invalid,
            )

        db.rollback()


def test_rejected_action_cannot_execute() -> None:
    with SessionLocal() as db:
        conversation, run = build_context(db)

        proposal = create_action_proposal(
            db,
            conversation_id=conversation.conversation_id,
            run_id=run.run_id,
            customer_id="CUS-1007",
            recommendation=retry_recommendation(),
        )

        reject_action(
            db,
            proposal.proposal_id,
            ApprovalDecisionInput(
                decided_by="support-operator"
            ),
        )

        with pytest.raises(PermissionError):
            execute_approved_action(
                db,
                proposal.proposal_id,
            )

        db.rollback()


def test_action_proposal_reuses_equivalent_pending_proposal_across_runs() -> None:
    with SessionLocal() as db:
        conversation, first_run = build_context(
            db
        )

        first = create_action_proposal(
            db,
            conversation_id=conversation.conversation_id,
            run_id=first_run.run_id,
            customer_id="CUS-1007",
            recommendation=retry_recommendation(),
        )

        second_run = AgentRun(
            conversation_id=conversation.conversation_id,
            resolution_status="ESCALATION_REQUIRED",
            issue_type="subscription_upgrade_failure",
            resolution_summary="Follow-up run.",
        )
        db.add(
            second_run
        )
        db.flush()

        second = create_action_proposal(
            db,
            conversation_id=conversation.conversation_id,
            run_id=second_run.run_id,
            customer_id="CUS-1007",
            recommendation=retry_recommendation(),
        )

        assert (
            second.proposal_id
            == first.proposal_id
        )
        assert (
            second.run_id
            == first_run.run_id
        )

        db.rollback()


def test_rejected_equivalent_proposal_allows_new_human_review() -> None:
    with SessionLocal() as db:
        conversation, first_run = build_context(
            db
        )

        first = create_action_proposal(
            db,
            conversation_id=conversation.conversation_id,
            run_id=first_run.run_id,
            customer_id="CUS-1007",
            recommendation=retry_recommendation(),
        )

        reject_action(
            db,
            first.proposal_id,
            ApprovalDecisionInput(
                decided_by="support-operator"
            ),
        )

        second_run = AgentRun(
            conversation_id=conversation.conversation_id,
            resolution_status="ESCALATION_REQUIRED",
            issue_type="subscription_upgrade_failure",
            resolution_summary="Customer requested another review.",
        )
        db.add(
            second_run
        )
        db.flush()

        second = create_action_proposal(
            db,
            conversation_id=conversation.conversation_id,
            run_id=second_run.run_id,
            customer_id="CUS-1007",
            recommendation=retry_recommendation(),
        )

        assert (
            second.proposal_id
            != first.proposal_id
        )
        assert (
            second.approval_status
            == "PENDING_APPROVAL"
        )

        db.rollback()


def test_rejected_subscription_retry_creates_pending_ticket_fallback() -> None:
    with SessionLocal() as db:
        conversation, run = build_context(db)
        proposal = create_action_proposal(
            db,
            conversation_id=conversation.conversation_id,
            run_id=run.run_id,
            customer_id="CUS-1007",
            recommendation=retry_recommendation(),
        )

        reject_action(
            db,
            proposal.proposal_id,
            ApprovalDecisionInput(
                decided_by="support-operator",
                reason="Specialist investigation required",
            ),
        )

        fallback = db.scalar(
            select(ActionProposal).where(
                ActionProposal.conversation_id == conversation.conversation_id,
                ActionProposal.action_name == "create_support_ticket",
                ActionProposal.approval_status == "PENDING_APPROVAL",
            )
        )

        assert proposal.approval_status == "REJECTED"
        assert fallback is not None
        assert fallback.issue_type == "subscription_remediation_rejected"
        args = json.loads(fallback.arguments_json)
        assert any(
            "Specialist investigation required" in item
            for item in args["evidence"]
        )
        db.rollback()


def test_rejecting_same_proposal_twice_does_not_duplicate_fallback_ticket() -> None:
    with SessionLocal() as db:
        conversation, run = build_context(db)
        proposal = create_action_proposal(
            db,
            conversation_id=conversation.conversation_id,
            run_id=run.run_id,
            customer_id="CUS-1007",
            recommendation=retry_recommendation(),
        )
        payload = ApprovalDecisionInput(
            decided_by="support-operator",
            reason="Evidence is insufficient",
        )

        reject_action(db, proposal.proposal_id, payload)
        reject_action(db, proposal.proposal_id, payload)

        fallbacks = list(
            db.scalars(
                select(ActionProposal).where(
                    ActionProposal.conversation_id == conversation.conversation_id,
                    ActionProposal.action_name == "create_support_ticket",
                    ActionProposal.issue_type == "subscription_remediation_rejected",
                )
            ).all()
        )
        assert len(fallbacks) == 1
        db.rollback()
