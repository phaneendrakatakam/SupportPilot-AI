import json

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.actions.schemas import ActionRecommendation
from app.actions.service import create_action_proposal
from app.db.models import (
    ActionExecution,
    ActionProposal,
    AgentRun,
    Conversation,
    Message,
    RefundReview,
    Subscription,
    SupportTicket,
    ToolExecution,
)
from app.db.session import SessionLocal
from app.main import app


client = TestClient(app)


def test_rejected_retry_falls_back_to_human_controlled_support_ticket() -> None:
    with SessionLocal() as db:
        conversation = Conversation(
            customer_id="CUS-1007",
            current_issue="subscription_upgrade_failure",
            resolution_status="ESCALATION_REQUIRED",
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
                reason="Successful Pro payment with failed subscription sync.",
                issue_type="subscription_upgrade_failure",
            ),
        )
        db.commit()
        conversation_id = conversation.conversation_id
        original_id = proposal.proposal_id

    try:
        rejected = client.post(
            f"/api/v1/actions/{original_id}/reject",
            json={
                "decided_by": "support-operator",
                "reason": "Specialist investigation required",
            },
        )
        assert rejected.status_code == 200
        assert rejected.json()["approval_status"] == "REJECTED"

        blocked = client.post(f"/api/v1/actions/{original_id}/execute")
        assert blocked.status_code == 403

        with SessionLocal() as db:
            subscription = db.scalar(
                select(Subscription).where(
                    Subscription.customer_id == "CUS-1007"
                )
            )
            assert subscription is not None
            assert subscription.plan == "BASIC"
            assert subscription.last_sync_status == "FAILED"

            fallback = db.scalar(
                select(ActionProposal).where(
                    ActionProposal.conversation_id == conversation_id,
                    ActionProposal.action_name == "create_support_ticket",
                    ActionProposal.approval_status == "PENDING_APPROVAL",
                )
            )
            assert fallback is not None
            fallback_id = fallback.proposal_id
            arguments = json.loads(fallback.arguments_json)
            assert any(
                "Specialist investigation required" in item
                for item in arguments["evidence"]
            )

        pending = client.get(
            f"/api/v1/support/conversations/{conversation_id}/case-status",
            params={"customer_id": "CUS-1007"},
        )
        assert pending.status_code == 200
        assert pending.json()["case_status"] == "UNDER_REVIEW"
        assert pending.json()["case_type"] == "SUPPORT_CASE"
        assert "proposed fix was not approved" in pending.json()["message"].lower()

        approved = client.post(
            f"/api/v1/actions/{fallback_id}/approve",
            json={"decided_by": "support-operator"},
        )
        assert approved.status_code == 200

        executed = client.post(f"/api/v1/actions/{fallback_id}/execute")
        assert executed.status_code == 200
        assert executed.json()["execution_status"] == "SUCCEEDED"
        assert executed.json()["verification_status"] == "VERIFIED"

        final = client.get(
            f"/api/v1/support/conversations/{conversation_id}/case-status",
            params={"customer_id": "CUS-1007"},
        )
        assert final.status_code == 200
        assert final.json()["case_status"] == "CASE_OPEN"
        assert final.json()["reference"].startswith("TKT-")

    finally:
        with SessionLocal() as db:
            run_ids = list(db.scalars(
                select(AgentRun.run_id).where(
                    AgentRun.conversation_id == conversation_id
                )
            ).all())
            proposal_ids = list(db.scalars(
                select(ActionProposal.proposal_id).where(
                    ActionProposal.conversation_id == conversation_id
                )
            ).all())
            if proposal_ids:
                db.execute(delete(ActionExecution).where(
                    ActionExecution.proposal_id.in_(proposal_ids)
                ))
                db.execute(delete(SupportTicket).where(
                    SupportTicket.proposal_id.in_(proposal_ids)
                ))
                db.execute(delete(RefundReview).where(
                    RefundReview.proposal_id.in_(proposal_ids)
                ))
                db.execute(delete(ActionProposal).where(
                    ActionProposal.proposal_id.in_(proposal_ids)
                ))
            if run_ids:
                db.execute(delete(ToolExecution).where(
                    ToolExecution.run_id.in_(run_ids)
                ))
            db.execute(delete(Message).where(
                Message.conversation_id == conversation_id
            ))
            db.execute(delete(AgentRun).where(
                AgentRun.conversation_id == conversation_id
            ))
            db.execute(delete(Conversation).where(
                Conversation.conversation_id == conversation_id
            ))
            db.commit()
