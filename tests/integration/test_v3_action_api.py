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
    Payment,
    RefundReview,
    Subscription,
    SupportTicket,
    ToolExecution,
)
from app.db.session import SessionLocal
from app.main import app


client = TestClient(app)


def create_context(
    customer_id: str,
    recommendation: ActionRecommendation,
):
    with SessionLocal() as db:
        conversation = Conversation(
            customer_id=customer_id
        )
        db.add(conversation)
        db.flush()

        run = AgentRun(
            conversation_id=conversation.conversation_id,
            resolution_status="ESCALATION_REQUIRED",
            issue_type=recommendation.issue_type,
            resolution_summary="V3 action API test.",
        )
        db.add(run)
        db.flush()

        proposal = create_action_proposal(
            db,
            conversation_id=conversation.conversation_id,
            run_id=run.run_id,
            customer_id=customer_id,
            recommendation=recommendation,
        )

        db.commit()

        return (
            conversation.conversation_id,
            run.run_id,
            proposal.proposal_id,
        )


def cleanup_context(
    conversation_id: str,
    *,
    restore_subscription: bool = False,
) -> None:
    with SessionLocal() as db:
        if restore_subscription:
            subscription = db.scalar(
                select(Subscription).where(
                    Subscription.customer_id
                    == "CUS-1007"
                )
            )
            if subscription is not None:
                subscription.plan = "BASIC"
                subscription.requested_plan = "PRO"
                subscription.last_sync_status = "FAILED"

        run_ids = list(
            db.scalars(
                select(AgentRun.run_id).where(
                    AgentRun.conversation_id
                    == conversation_id
                )
            ).all()
        )

        if run_ids:
            proposal_ids = list(
                db.scalars(
                    select(ActionProposal.proposal_id).where(
                        ActionProposal.run_id.in_(run_ids)
                    )
                ).all()
            )

            if proposal_ids:
                db.execute(
                    delete(ActionExecution).where(
                        ActionExecution.proposal_id.in_(proposal_ids)
                    )
                )
                db.execute(
                    delete(SupportTicket).where(
                        SupportTicket.proposal_id.in_(proposal_ids)
                    )
                )
                db.execute(
                    delete(RefundReview).where(
                        RefundReview.proposal_id.in_(proposal_ids)
                    )
                )
                db.execute(
                    delete(ActionProposal).where(
                        ActionProposal.proposal_id.in_(proposal_ids)
                    )
                )

            db.execute(
                delete(ToolExecution).where(
                    ToolExecution.run_id.in_(run_ids)
                )
            )

        db.execute(
            delete(Message).where(
                Message.conversation_id
                == conversation_id
            )
        )
        db.execute(
            delete(AgentRun).where(
                AgentRun.conversation_id
                == conversation_id
            )
        )
        db.execute(
            delete(Conversation).where(
                Conversation.conversation_id
                == conversation_id
            )
        )

        db.commit()


def retry_recommendation() -> ActionRecommendation:
    return ActionRecommendation(
        action_name="retry_subscription_sync",
        arguments={
            "customer_id": "CUS-1007",
            "requested_plan": "PRO",
        },
        reason="Paid Pro upgrade has a failed subscription synchronization.",
        issue_type="subscription_upgrade_failure",
    )


def test_execute_endpoint_requires_human_approval() -> None:
    conversation_id, _run_id, proposal_id = create_context(
        "CUS-1007",
        retry_recommendation(),
    )

    try:
        response = client.post(
            f"/api/v1/actions/{proposal_id}/execute"
        )

        assert response.status_code == 403
        assert "explicit human approval" in response.json()["detail"]

    finally:
        cleanup_context(
            conversation_id
        )


def test_approve_and_execute_retry_subscription_sync() -> None:
    conversation_id, _run_id, proposal_id = create_context(
        "CUS-1007",
        retry_recommendation(),
    )

    try:
        approve_response = client.post(
            f"/api/v1/actions/{proposal_id}/approve",
            json={
                "decided_by": "support-operator",
            },
        )

        assert approve_response.status_code == 200
        assert (
            approve_response.json()["approval_status"]
            == "APPROVED"
        )

        execute_response = client.post(
            f"/api/v1/actions/{proposal_id}/execute"
        )

        assert execute_response.status_code == 200

        body = execute_response.json()

        assert body["execution_status"] == "SUCCEEDED"
        assert body["verification_status"] == "VERIFIED"
        assert body["after_state"]["plan"] == "PRO"
        assert body["after_state"]["last_sync_status"] == "SUCCESS"

    finally:
        cleanup_context(
            conversation_id,
            restore_subscription=True,
        )


def test_rejected_action_cannot_execute() -> None:
    conversation_id, _run_id, proposal_id = create_context(
        "CUS-1007",
        retry_recommendation(),
    )

    try:
        reject_response = client.post(
            f"/api/v1/actions/{proposal_id}/reject",
            json={
                "decided_by": "support-operator",
            },
        )

        assert reject_response.status_code == 200
        assert (
            reject_response.json()["approval_status"]
            == "REJECTED"
        )

        execute_response = client.post(
            f"/api/v1/actions/{proposal_id}/execute"
        )

        assert execute_response.status_code == 403

    finally:
        cleanup_context(
            conversation_id
        )


def test_approved_support_ticket_action_creates_verified_ticket() -> None:
    recommendation = ActionRecommendation(
        action_name="create_support_ticket",
        arguments={
            "customer_id": "CUS-1007",
            "issue_type": "cross_system_plan_conflict",
            "summary": "Payment and subscription plan evidence conflict.",
            "priority": "HIGH",
            "evidence": [
                "Payment plan differs from requested plan.",
                "Subscription synchronization requires review.",
            ],
        },
        reason="Human support review is required.",
        issue_type="cross_system_plan_conflict",
    )

    conversation_id, _run_id, proposal_id = create_context(
        "CUS-1007",
        recommendation,
    )

    try:
        client.post(
            f"/api/v1/actions/{proposal_id}/approve",
            json={
                "decided_by": "support-operator",
            },
        )

        response = client.post(
            f"/api/v1/actions/{proposal_id}/execute"
        )

        assert response.status_code == 200

        body = response.json()

        assert body["execution_status"] == "SUCCEEDED"
        assert body["verification_status"] == "VERIFIED"
        assert body["result"]["ticket_number"].startswith("TKT-")
        assert body["after_state"]["status"] == "OPEN"

        with SessionLocal() as db:
            ticket = db.scalar(
                select(SupportTicket).where(
                    SupportTicket.proposal_id
                    == proposal_id
                )
            )

            assert ticket is not None
            assert json.loads(ticket.evidence_json)

    finally:
        cleanup_context(
            conversation_id
        )


def test_refund_review_action_does_not_modify_payment() -> None:
    with SessionLocal() as db:
        payment_before = db.get(
            Payment,
            "PAY-3002",
        )
        assert payment_before is not None
        before_status = payment_before.status

    recommendation = ActionRecommendation(
        action_name="request_refund_review",
        arguments={
            "customer_id": "CUS-1002",
            "payment_id": "PAY-3002",
            "reason": "Customer explicitly requested a refund review.",
        },
        reason="Successful payment verified; human refund review requested.",
        issue_type="payment_status_verified",
    )

    conversation_id, _run_id, proposal_id = create_context(
        "CUS-1002",
        recommendation,
    )

    try:
        client.post(
            f"/api/v1/actions/{proposal_id}/approve",
            json={
                "decided_by": "support-operator",
            },
        )

        response = client.post(
            f"/api/v1/actions/{proposal_id}/execute"
        )

        assert response.status_code == 200

        body = response.json()

        assert body["execution_status"] == "SUCCEEDED"
        assert body["verification_status"] == "VERIFIED"
        assert body["result"]["review_number"].startswith("RR-")
        assert (
            body["verification_result"]["payment_unchanged"]
            is True
        )

        with SessionLocal() as db:
            payment_after = db.get(
                Payment,
                "PAY-3002",
            )
            review = db.scalar(
                select(RefundReview).where(
                    RefundReview.proposal_id
                    == proposal_id
                )
            )

            assert payment_after.status == before_status
            assert review is not None
            assert review.status == "PENDING_REVIEW"

    finally:
        cleanup_context(
            conversation_id
        )


def test_get_action_returns_proposal_and_execution() -> None:
    conversation_id, _run_id, proposal_id = create_context(
        "CUS-1007",
        retry_recommendation(),
    )

    try:
        response = client.get(
            f"/api/v1/actions/{proposal_id}"
        )

        assert response.status_code == 200
        assert response.json()["proposal"]["proposal_id"] == proposal_id
        assert response.json()["execution"] is None

    finally:
        cleanup_context(
            conversation_id
        )
