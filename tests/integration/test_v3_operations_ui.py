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
    SupportTicket,
    ToolExecution,
)
from app.db.session import SessionLocal
from app.main import app


client = TestClient(app)


def create_queue_context():
    recommendation = ActionRecommendation(
        action_name="create_support_ticket",
        arguments={
            "customer_id": "CUS-1007",
            "issue_type": "operations_queue_test",
            "summary": "Human review queue integration test.",
            "priority": "HIGH",
            "evidence": [
                "Verified synthetic test evidence.",
            ],
        },
        reason="Test human review queue proposal.",
        issue_type="operations_queue_test",
    )

    with SessionLocal() as db:
        conversation = Conversation(
            customer_id="CUS-1007"
        )
        db.add(conversation)
        db.flush()

        run = AgentRun(
            conversation_id=conversation.conversation_id,
            request_message="Create a human review queue test case.",
            resolution_status="ESCALATION_REQUIRED",
            issue_type=recommendation.issue_type,
            resolution_summary="Operations UI queue test.",
        )
        db.add(run)
        db.flush()

        proposal = create_action_proposal(
            db,
            conversation_id=conversation.conversation_id,
            run_id=run.run_id,
            customer_id="CUS-1007",
            recommendation=recommendation,
        )

        db.commit()

        return (
            conversation.conversation_id,
            proposal.proposal_id,
        )


def cleanup_queue_context(
    conversation_id: str,
) -> None:
    with SessionLocal() as db:
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


def test_operations_ui_is_available() -> None:
    response = client.get(
        "/operations"
    )

    assert response.status_code == 200
    assert "Human Review Queue" in response.text
    assert "Agent Inspector" in response.text
    assert "Controlled action" in response.text
    assert "What this AI turn resolved" in response.text
    assert "overall customer case" in response.text
    assert "Customer UI" not in response.text
    assert "Engineering Inspector" not in response.text
    assert "Optional technical details" in response.text


def test_operations_assets_use_v3_action_apis() -> None:
    javascript = client.get(
        "/static/operations.js"
    )
    stylesheet = client.get(
        "/static/operations.css"
    )

    assert javascript.status_code == 200
    assert stylesheet.status_code == 200
    assert "/api/v1/actions?limit=100" in javascript.text
    assert "/api/v1/debug/runs/" in javascript.text
    assert "/execute" in javascript.text
    assert "Overall case" in javascript.text
    assert "Awaiting human approval" in javascript.text
    assert ".review-item" in stylesheet.text
    assert ".topbar-links" not in stylesheet.text
    assert "retry_subscription_sync" not in javascript.text[
        javascript.text.find("function renderActionRecommendation"):javascript.text.find("function renderApprovalControls")
        if "function renderApprovalControls" in javascript.text
        else len(javascript.text)
    ]


def test_action_queue_endpoint_returns_pending_review() -> None:
    conversation_id, proposal_id = create_queue_context()

    try:
        response = client.get(
            "/api/v1/actions",
            params={
                "approval_status": "PENDING_APPROVAL",
                "limit": 100,
            },
        )

        assert response.status_code == 200

        matching = [
            item
            for item in response.json()
            if item["proposal"]["proposal_id"]
            == proposal_id
        ]

        assert len(matching) == 1
        assert (
            matching[0]["proposal"]["approval_status"]
            == "PENDING_APPROVAL"
        )
        assert matching[0]["execution"] is None

    finally:
        cleanup_queue_context(
            conversation_id
        )


def test_operations_rejection_requires_reason_and_prepares_fallback_flow() -> None:
    html = client.get("/operations")
    javascript = client.get("/static/operations.js")

    assert html.status_code == 200
    assert javascript.status_code == 200
    assert 'id="reject-dialog"' in html.text
    assert "Why are you rejecting this action?" in html.text
    assert "Specialist investigation required" in html.text
    assert "rejectionReason" in javascript.text
    assert "decisionReason" in javascript.text
    assert "create_support_ticket" in javascript.text



def test_operations_readability_polish_formats_human_review_data() -> None:
    html = client.get("/operations")
    javascript = client.get("/static/operations.js")
    stylesheet = client.get("/static/operations.css")

    assert html.status_code == 200
    assert javascript.status_code == 200
    assert stylesheet.status_code == 200

    assert (
        "/static/operations.css?v=20260904-v3-operations-polish-1"
        in html.text
    )
    assert (
        "/static/operations.js?v=20260904-v3-operations-polish-1"
        in html.text
    )

    assert "appendActionArgument" in javascript.text
    assert "argument-list" in javascript.text
    assert "Before action" in javascript.text
    assert "After action" in javascript.text
    assert "Specialist support handoff" in javascript.text
    assert "Billing review handoff" in javascript.text
    assert "The refund was not issued automatically." in javascript.text

    assert ".action-argument-row" in stylesheet.text
    assert ".argument-list" in stylesheet.text
    assert ".state-value.changed" in stylesheet.text
    assert ".handoff-status-chip" in stylesheet.text
    assert ".technical-context-item" in stylesheet.text
