import pytest

from app.actions.schemas import ActionRecommendation
from app.actions.service import create_action_proposal
from app.db.models import AgentRun, Conversation
from app.db.session import SessionLocal


def test_action_arguments_cannot_target_another_customer() -> None:
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

        recommendation = ActionRecommendation(
            action_name="retry_subscription_sync",
            arguments={
                "customer_id": "CUS-1002",
                "requested_plan": "PRO",
            },
            reason="Cross-customer action must be blocked.",
            issue_type="subscription_upgrade_failure",
        )

        with pytest.raises(
            ValueError,
            match="proposal customer",
        ):
            create_action_proposal(
                db,
                conversation_id=conversation.conversation_id,
                run_id=run.run_id,
                customer_id="CUS-1007",
                recommendation=recommendation,
            )

        db.rollback()
