import json

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
    RefundReview,
    Subscription,
    SupportTicket,
    ToolExecution,
)
from app.db.session import SessionLocal
from app.main import app


client = TestClient(app)


def _recommendation() -> ActionRecommendation:
    return ActionRecommendation(
        action_name="retry_subscription_sync",
        arguments={
            "customer_id":
                "CUS-1007",
            "requested_plan":
                "PRO",
        },
        reason=(
            "Paid Pro upgrade has a failed "
            "subscription synchronization."
        ),
        issue_type=(
            "subscription_upgrade_failure"
        ),
    )


def _create_context() -> tuple[
    str,
    str,
]:
    recommendation = _recommendation()

    with SessionLocal() as db:
        conversation = Conversation(
            customer_id="CUS-1007",
            current_issue=(
                recommendation.issue_type
            ),
            resolution_status=(
                "ESCALATION_REQUIRED"
            ),
        )
        db.add(conversation)
        db.flush()

        run = AgentRun(
            conversation_id=(
                conversation.conversation_id
            ),
            resolution_status=(
                "ESCALATION_REQUIRED"
            ),
            issue_type=(
                recommendation.issue_type
            ),
            resolution_summary=(
                "Customer case-status test."
            ),
        )
        db.add(run)
        db.flush()

        proposal = create_action_proposal(
            db,
            conversation_id=(
                conversation.conversation_id
            ),
            run_id=run.run_id,
            customer_id="CUS-1007",
            recommendation=recommendation,
        )

        db.commit()

        return (
            conversation.conversation_id,
            proposal.proposal_id,
        )


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
            subscription.last_sync_status = (
                "FAILED"
            )

        db.commit()


def _cleanup(
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

        proposal_ids = list(
            db.scalars(
                select(
                    ActionProposal.proposal_id
                ).where(
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

    _restore_subscription()


def _case_status(
    conversation_id: str,
    customer_id: str = "CUS-1007",
):
    return client.get(
        (
            "/api/v1/support/conversations/"
            f"{conversation_id}/case-status"
        ),
        params={
            "customer_id":
                customer_id,
        },
    )


def test_pending_case_status_is_customer_safe() -> None:
    conversation_id, _proposal_id = (
        _create_context()
    )

    try:
        response = _case_status(
            conversation_id
        )

        assert response.status_code == 200

        body = response.json()

        assert (
            body["case_status"]
            == "UNDER_REVIEW"
        )
        assert (
            body["case_type"]
            == "SUBSCRIPTION_UPDATE"
        )

        assert "proposal_id" not in body
        assert "action_name" not in body
        assert "approval_status" not in body
        assert "execution_id" not in body

    finally:
        _cleanup(
            conversation_id
        )


def test_approval_alone_keeps_customer_under_review() -> None:
    conversation_id, proposal_id = (
        _create_context()
    )

    try:
        approve = client.post(
            (
                f"/api/v1/actions/"
                f"{proposal_id}/approve"
            ),
            json={
                "decided_by":
                    "support-operator",
            },
        )

        assert approve.status_code == 200

        response = _case_status(
            conversation_id
        )

        assert response.status_code == 200
        assert (
            response.json()["case_status"]
            == "UNDER_REVIEW"
        )

        with SessionLocal() as db:
            subscription = db.scalar(
                select(Subscription).where(
                    Subscription.customer_id
                    == "CUS-1007"
                )
            )

            assert subscription is not None
            assert subscription.plan == "BASIC"
            assert (
                subscription.last_sync_status
                == "FAILED"
            )

    finally:
        _cleanup(
            conversation_id
        )


def test_verified_retry_resolves_customer_case_and_persists_message() -> None:
    conversation_id, proposal_id = (
        _create_context()
    )

    try:
        client.post(
            (
                f"/api/v1/actions/"
                f"{proposal_id}/approve"
            ),
            json={
                "decided_by":
                    "support-operator",
            },
        )

        execute = client.post(
            (
                f"/api/v1/actions/"
                f"{proposal_id}/execute"
            )
        )

        assert execute.status_code == 200
        assert (
            execute.json()[
                "verification_status"
            ]
            == "VERIFIED"
        )

        response = _case_status(
            conversation_id
        )

        assert response.status_code == 200

        body = response.json()

        assert (
            body["case_status"]
            == "RESOLVED"
        )
        assert body["current_plan"] == "PRO"
        assert (
            "verified successfully"
            in body["message"]
        )

        with SessionLocal() as db:
            conversation = db.get(
                Conversation,
                conversation_id,
            )

            assert conversation is not None
            assert (
                conversation.resolution_status
                == "RESOLVED"
            )

            final_message = db.scalar(
                select(Message).where(
                    Message.conversation_id
                    == conversation_id,
                    Message.role
                    == "assistant",
                    Message.content
                    == body["customer_message"],
                )
            )

            assert final_message is not None

    finally:
        _cleanup(
            conversation_id
        )


def test_rejected_case_moves_to_fallback_review_without_account_change() -> None:
    conversation_id, proposal_id = (
        _create_context()
    )

    try:
        rejected = client.post(
            (
                f"/api/v1/actions/"
                f"{proposal_id}/reject"
            ),
            json={
                "decided_by":
                    "support-operator",
                "reason":
                    "Specialist investigation required",
            },
        )

        assert rejected.status_code == 200
        assert (
            rejected.json()["approval_status"]
            == "REJECTED"
        )

        response = _case_status(
            conversation_id
        )

        assert response.status_code == 200

        body = response.json()

        # Rejection blocks the original remediation, but V3 now prepares
        # a separate human-controlled support-ticket proposal. Therefore the
        # overall customer case remains actively UNDER_REVIEW rather than
        # stopping at NEEDS_SUPPORT.
        assert (
            body["case_status"]
            == "UNDER_REVIEW"
        )
        assert (
            body["case_type"]
            == "SUPPORT_CASE"
        )
        assert (
            "proposed fix was not approved"
            in body["message"].lower()
        )

        with SessionLocal() as db:
            subscription = db.scalar(
                select(Subscription).where(
                    Subscription.customer_id
                    == "CUS-1007"
                )
            )

            assert subscription is not None
            assert subscription.plan == "BASIC"
            assert (
                subscription.last_sync_status
                == "FAILED"
            )

            fallback = db.scalar(
                select(ActionProposal).where(
                    ActionProposal.conversation_id
                    == conversation_id,
                    ActionProposal.action_name
                    == "create_support_ticket",
                    ActionProposal.approval_status
                    == "PENDING_APPROVAL",
                )
            )

            assert fallback is not None
            assert (
                fallback.issue_type
                == "subscription_remediation_rejected"
            )

    finally:
        _cleanup(
            conversation_id
        )


def test_case_status_enforces_customer_isolation() -> None:
    conversation_id, _proposal_id = (
        _create_context()
    )

    try:
        response = _case_status(
            conversation_id,
            customer_id="CUS-1002",
        )

        assert response.status_code == 403

    finally:
        _cleanup(
            conversation_id
        )


def test_customer_case_status_prefers_verified_refund_over_newer_legacy_duplicate() -> None:
    recommendation = ActionRecommendation(
        action_name="request_refund_review",
        arguments={
            "customer_id": "CUS-1002",
            "payment_id": "PAY-3002",
            "reason": "Customer requested a refund review.",
        },
        reason=(
            "Verified successful payment and explicit refund request."
        ),
        issue_type="payment_status_verified",
    )

    with SessionLocal() as db:
        conversation = Conversation(
            customer_id="CUS-1002",
            current_issue="payment_status_verified",
            resolution_status="RESOLVED",
        )
        db.add(conversation)
        db.flush()

        first_run = AgentRun(
            conversation_id=conversation.conversation_id,
            resolution_status="RESOLVED",
            issue_type="payment_status_verified",
            resolution_summary="Refund payment verified.",
        )
        db.add(first_run)
        db.flush()

        verified_proposal = create_action_proposal(
            db,
            conversation_id=conversation.conversation_id,
            run_id=first_run.run_id,
            customer_id="CUS-1002",
            recommendation=recommendation,
        )

        db.commit()

        conversation_id = conversation.conversation_id
        verified_proposal_id = verified_proposal.proposal_id

    try:
        approved = client.post(
            f"/api/v1/actions/{verified_proposal_id}/approve",
            json={
                "decided_by": "support-operator",
            },
        )
        assert approved.status_code == 200

        executed = client.post(
            f"/api/v1/actions/{verified_proposal_id}/execute"
        )
        assert executed.status_code == 200
        assert executed.json()["verification_status"] == "VERIFIED"

        with SessionLocal() as db:
            review = db.scalar(
                select(RefundReview).where(
                    RefundReview.proposal_id
                    == verified_proposal_id
                )
            )
            assert review is not None
            review_number = review.review_number

            duplicate_run = AgentRun(
                conversation_id=conversation_id,
                resolution_status="RESOLVED",
                issue_type="payment_status_verified",
                resolution_summary="Legacy duplicate follow-up run.",
            )
            db.add(duplicate_run)
            db.flush()

            duplicate = ActionProposal(
                conversation_id=conversation_id,
                run_id=duplicate_run.run_id,
                customer_id="CUS-1002",
                action_name="request_refund_review",
                arguments_json=json.dumps(
                    recommendation.arguments
                ),
                reason=recommendation.reason,
                issue_type=recommendation.issue_type,
                approval_required=True,
                approval_status="PENDING_APPROVAL",
                idempotency_key=(
                    "legacy-refund-duplicate-"
                    + duplicate_run.run_id
                ),
            )
            db.add(duplicate)
            db.commit()

        response = client.get(
            (
                "/api/v1/support/conversations/"
                f"{conversation_id}/case-status"
            ),
            params={
                "customer_id": "CUS-1002",
            },
        )

        assert response.status_code == 200
        body = response.json()

        assert body["case_status"] == "REFUND_REVIEW_OPEN"
        assert body["case_type"] == "REFUND_REVIEW"
        assert body["reference"] == review_number
        assert (
            "No refund was issued automatically"
            in body["message"]
        )

    finally:
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
