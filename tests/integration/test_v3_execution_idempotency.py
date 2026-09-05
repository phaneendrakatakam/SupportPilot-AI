from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.actions.schemas import (
    ActionRecommendation,
)
from app.actions.service import (
    create_action_proposal,
)
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


def _create_context(
    *,
    customer_id: str,
    recommendation: ActionRecommendation,
) -> tuple[str, str]:
    with SessionLocal() as db:
        conversation = Conversation(
            customer_id=customer_id,
            current_issue=recommendation.issue_type,
            resolution_status="ESCALATION_REQUIRED",
        )
        db.add(conversation)
        db.flush()

        run = AgentRun(
            conversation_id=conversation.conversation_id,
            request_message="Idempotency hardening test.",
            resolution_status="ESCALATION_REQUIRED",
            issue_type=recommendation.issue_type,
            resolution_summary="Controlled action requires human approval.",
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
            proposal.proposal_id,
        )


def _approve(proposal_id: str) -> None:
    response = client.post(
        f"/api/v1/actions/{proposal_id}/approve",
        json={
            "decided_by":
                "support-operator",
        },
    )

    assert response.status_code == 200
    assert (
        response.json()["approval_status"]
        == "APPROVED"
    )


def _execute(proposal_id: str):
    response = client.post(
        f"/api/v1/actions/{proposal_id}/execute"
    )

    assert response.status_code == 200
    return response


def _restore_subscription() -> None:
    with SessionLocal() as db:
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

        db.commit()


def _cleanup(
    conversation_id: str,
    *,
    restore_subscription: bool = False,
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

        proposal_ids = list(
            db.scalars(
                select(ActionProposal.proposal_id).where(
                    ActionProposal.conversation_id
                    == conversation_id
                )
            ).all()
        )

        if proposal_ids:
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

        if run_ids:
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

    if restore_subscription:
        _restore_subscription()


def test_retry_subscription_sync_duplicate_execute_reuses_execution_and_message() -> None:
    recommendation = ActionRecommendation(
        action_name="retry_subscription_sync",
        arguments={
            "customer_id":
                "CUS-1007",
            "requested_plan":
                "PRO",
        },
        reason=(
            "Successful Pro payment with failed subscription synchronization."
        ),
        issue_type="subscription_upgrade_failure",
    )

    conversation_id, proposal_id = _create_context(
        customer_id="CUS-1007",
        recommendation=recommendation,
    )

    try:
        _approve(
            proposal_id
        )

        first = _execute(
            proposal_id
        )
        second = _execute(
            proposal_id
        )

        first_body = first.json()
        second_body = second.json()

        assert (
            first_body["execution_id"]
            == second_body["execution_id"]
        )
        assert (
            first_body["execution_status"]
            == "SUCCEEDED"
        )
        assert (
            first_body["verification_status"]
            == "VERIFIED"
        )
        assert (
            second_body["execution_status"]
            == "SUCCEEDED"
        )
        assert (
            second_body["verification_status"]
            == "VERIFIED"
        )

        with SessionLocal() as db:
            executions = list(
                db.scalars(
                    select(ActionExecution).where(
                        ActionExecution.proposal_id
                        == proposal_id
                    )
                ).all()
            )

            subscription = db.scalar(
                select(Subscription).where(
                    Subscription.customer_id
                    == "CUS-1007"
                )
            )

            messages = list(
                db.scalars(
                    select(Message).where(
                        Message.conversation_id
                        == conversation_id,
                        Message.role
                        == "assistant",
                    )
                ).all()
            )

            assert len(executions) == 1
            assert subscription is not None
            assert subscription.plan == "PRO"
            assert (
                subscription.last_sync_status
                == "SUCCESS"
            )

            final_messages = [
                item
                for item in messages
                if (
                    "Your account has now been updated to **PRO**."
                    in item.content
                )
            ]

            assert len(final_messages) == 1

    finally:
        _cleanup(
            conversation_id,
            restore_subscription=True,
        )


def test_create_support_ticket_duplicate_execute_creates_one_ticket() -> None:
    recommendation = ActionRecommendation(
        action_name="create_support_ticket",
        arguments={
            "customer_id":
                "CUS-1005",
            "issue_type":
                "subscription_upgrade_payment_unverified",
            "summary": (
                "Requested Pro upgrade is not applied, subscription sync is "
                "failed, and no matching payment record could be verified."
            ),
            "priority":
                "HIGH",
            "evidence": [
                "Current plan: BASIC.",
                "Requested plan: PRO.",
                "Subscription sync: FAILED.",
                "Payment lookup: NOT_FOUND.",
            ],
        },
        reason=(
            "Billing and subscription state require specialist reconciliation."
        ),
        issue_type=(
            "subscription_upgrade_payment_unverified"
        ),
    )

    conversation_id, proposal_id = _create_context(
        customer_id="CUS-1005",
        recommendation=recommendation,
    )

    try:
        _approve(
            proposal_id
        )

        first = _execute(
            proposal_id
        )
        second = _execute(
            proposal_id
        )

        assert (
            first.json()["execution_id"]
            == second.json()["execution_id"]
        )
        assert (
            first.json()["verification_status"]
            == "VERIFIED"
        )
        assert (
            second.json()["verification_status"]
            == "VERIFIED"
        )

        with SessionLocal() as db:
            executions = list(
                db.scalars(
                    select(ActionExecution).where(
                        ActionExecution.proposal_id
                        == proposal_id
                    )
                ).all()
            )
            tickets = list(
                db.scalars(
                    select(SupportTicket).where(
                        SupportTicket.proposal_id
                        == proposal_id
                    )
                ).all()
            )

            assert len(executions) == 1
            assert len(tickets) == 1
            assert tickets[0].status == "OPEN"
            assert (
                tickets[0].ticket_number
                .startswith("TKT-")
            )

    finally:
        _cleanup(
            conversation_id
        )


def test_refund_review_duplicate_execute_creates_one_review_and_never_refunds() -> None:
    recommendation = ActionRecommendation(
        action_name="request_refund_review",
        arguments={
            "customer_id":
                "CUS-1002",
            "payment_id":
                "PAY-3002",
            "reason": (
                "Customer explicitly requested a refund after the successful "
                "payment was verified."
            ),
        },
        reason=(
            "A human refund review is appropriate; no refund is automatic."
        ),
        issue_type="refund_request",
    )

    conversation_id, proposal_id = _create_context(
        customer_id="CUS-1002",
        recommendation=recommendation,
    )

    try:
        with SessionLocal() as db:
            payment_before = db.get(
                Payment,
                "PAY-3002",
            )
            assert payment_before is not None
            original_status = payment_before.status

        _approve(
            proposal_id
        )

        first = _execute(
            proposal_id
        )
        second = _execute(
            proposal_id
        )

        assert (
            first.json()["execution_id"]
            == second.json()["execution_id"]
        )
        assert (
            first.json()["verification_status"]
            == "VERIFIED"
        )
        assert (
            second.json()["verification_status"]
            == "VERIFIED"
        )

        with SessionLocal() as db:
            executions = list(
                db.scalars(
                    select(ActionExecution).where(
                        ActionExecution.proposal_id
                        == proposal_id
                    )
                ).all()
            )
            reviews = list(
                db.scalars(
                    select(RefundReview).where(
                        RefundReview.proposal_id
                        == proposal_id
                    )
                ).all()
            )
            payment_after = db.get(
                Payment,
                "PAY-3002",
            )

            assert len(executions) == 1
            assert len(reviews) == 1
            assert (
                reviews[0].status
                == "PENDING_REVIEW"
            )
            assert (
                reviews[0].review_number
                .startswith("RR-")
            )

            assert payment_after is not None
            assert (
                payment_after.status
                == original_status
                == "SUCCESS"
            )

    finally:
        _cleanup(
            conversation_id
        )
