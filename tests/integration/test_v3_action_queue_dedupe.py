import json

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

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


def test_operator_queue_collapses_old_equivalent_pending_duplicates() -> None:
    with SessionLocal() as db:
        conversation = Conversation(
            customer_id="CUS-1002",
            current_issue="refund_request",
            resolution_status="RESOLVED",
        )
        db.add(
            conversation
        )
        db.flush()

        run_one = AgentRun(
            conversation_id=conversation.conversation_id,
            request_message="I want a refund.",
            resolution_status="RESOLVED",
            issue_type="payment_status_verified",
            resolution_summary="Payment verified.",
        )
        run_two = AgentRun(
            conversation_id=conversation.conversation_id,
            request_message="Has my refund been processed?",
            resolution_status="RESOLVED",
            issue_type="payment_status_verified",
            resolution_summary="Payment verified again.",
        )
        db.add_all(
            [
                run_one,
                run_two,
            ]
        )
        db.flush()

        arguments = {
            "customer_id":
                "CUS-1002",
            "payment_id":
                "PAY-3002",
            "reason":
                "Customer requested a refund review.",
        }

        first = ActionProposal(
            conversation_id=conversation.conversation_id,
            run_id=run_one.run_id,
            customer_id="CUS-1002",
            action_name="request_refund_review",
            arguments_json=json.dumps(arguments),
            reason="Verified successful payment.",
            issue_type="payment_status_verified",
            approval_required=True,
            approval_status="PENDING_APPROVAL",
            idempotency_key=(
                "queue-dedupe-test-1-"
                + conversation.conversation_id
            ),
        )
        second = ActionProposal(
            conversation_id=conversation.conversation_id,
            run_id=run_two.run_id,
            customer_id="CUS-1002",
            action_name="request_refund_review",
            arguments_json=json.dumps(arguments),
            reason="Verified successful payment.",
            issue_type="payment_status_verified",
            approval_required=True,
            approval_status="PENDING_APPROVAL",
            idempotency_key=(
                "queue-dedupe-test-2-"
                + conversation.conversation_id
            ),
        )

        db.add_all(
            [
                first,
                second,
            ]
        )
        db.commit()

        conversation_id = (
            conversation.conversation_id
        )
        proposal_ids = [
            first.proposal_id,
            second.proposal_id,
        ]
        run_ids = [
            run_one.run_id,
            run_two.run_id,
        ]

    try:
        response = client.get(
            "/api/v1/actions",
            params={
                "limit":
                    200,
            },
        )

        assert response.status_code == 200

        matching = [
            item
            for item in response.json()
            if (
                item["proposal"]["conversation_id"]
                == conversation_id
                and item["proposal"]["action_name"]
                == "request_refund_review"
            )
        ]

        assert len(
            matching
        ) == 1

    finally:
        with SessionLocal() as db:
            db.execute(
                delete(ActionExecution).where(
                    ActionExecution.proposal_id.in_(
                        proposal_ids
                    )
                )
            )
            db.execute(
                delete(SupportTicket).where(
                    SupportTicket.proposal_id.in_(
                        proposal_ids
                    )
                )
            )
            db.execute(
                delete(RefundReview).where(
                    RefundReview.proposal_id.in_(
                        proposal_ids
                    )
                )
            )
            db.execute(
                delete(ActionProposal).where(
                    ActionProposal.proposal_id.in_(
                        proposal_ids
                    )
                )
            )
            db.execute(
                delete(ToolExecution).where(
                    ToolExecution.run_id.in_(
                        run_ids
                    )
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
                    AgentRun.run_id.in_(
                        run_ids
                    )
                )
            )
            db.execute(
                delete(Conversation).where(
                    Conversation.conversation_id
                    == conversation_id
                )
            )
            db.commit()
