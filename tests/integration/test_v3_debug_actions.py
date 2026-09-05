from fastapi.testclient import TestClient

from app.actions.schemas import ActionRecommendation
from app.actions.service import create_action_proposal
from app.db.models import (
    ActionExecution,
    ActionProposal,
    AgentRun,
    Conversation,
)
from app.db.session import SessionLocal
from app.main import app


client = TestClient(app)


def test_debug_run_exposes_v3_action_proposal() -> None:
    with SessionLocal() as db:
        conversation = Conversation(
            customer_id="CUS-1007"
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
                reason="Paid upgrade has a failed sync.",
                issue_type="subscription_upgrade_failure",
            ),
        )

        conversation_id = conversation.conversation_id
        run_id = run.run_id
        proposal_id = proposal.proposal_id
        db.commit()

    try:
        response = client.get(
            f"/api/v1/debug/runs/{run_id}"
        )

        assert response.status_code == 200

        body = response.json()

        assert len(body["action_proposals"]) == 1
        assert (
            body["action_proposals"][0]["proposal_id"]
            == proposal_id
        )
        assert (
            body["action_proposals"][0]["approval_status"]
            == "PENDING_APPROVAL"
        )

    finally:
        with SessionLocal() as db:
            db.query(ActionExecution).filter(
                ActionExecution.proposal_id
                == proposal_id
            ).delete(
                synchronize_session=False
            )
            db.query(ActionProposal).filter(
                ActionProposal.proposal_id
                == proposal_id
            ).delete(
                synchronize_session=False
            )
            db.query(AgentRun).filter(
                AgentRun.run_id
                == run_id
            ).delete(
                synchronize_session=False
            )
            db.query(Conversation).filter(
                Conversation.conversation_id
                == conversation_id
            ).delete(
                synchronize_session=False
            )
            db.commit()
