import json

from sqlalchemy import select

import app.actions.service as action_service
from app.actions.schemas import (
    ActionRecommendation,
    ApprovalDecisionInput,
    ControlledActionResult,
)
from app.actions.service import (
    approve_action,
    create_action_proposal,
    execute_approved_action,
)
from app.db.models import (
    ActionExecution,
    AgentRun,
    Conversation,
    Payment,
    RefundReview,
    Subscription,
    SupportTicket,
)
from app.db.session import SessionLocal
from app.services.customer_case import (
    build_customer_case_snapshot,
)


def _context(
    db,
    customer_id: str,
    *,
    issue_type: str,
):
    conversation = Conversation(
        customer_id=customer_id,
        current_issue=issue_type,
        resolution_status="ESCALATION_REQUIRED",
    )
    db.add(
        conversation
    )
    db.flush()

    run = AgentRun(
        conversation_id=conversation.conversation_id,
        resolution_status="ESCALATION_REQUIRED",
        issue_type=issue_type,
        resolution_summary="Controlled-action failure hardening test.",
    )
    db.add(
        run
    )
    db.flush()

    return conversation, run


def _retry_recommendation() -> ActionRecommendation:
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


def _ticket_recommendation() -> ActionRecommendation:
    return ActionRecommendation(
        action_name="create_support_ticket",
        arguments={
            "customer_id": "CUS-1005",
            "issue_type":
                "subscription_upgrade_payment_unverified",
            "summary": (
                "Requested Pro upgrade is not applied and billing evidence "
                "requires specialist reconciliation."
            ),
            "priority": "HIGH",
            "evidence": [
                "Current plan: BASIC.",
                "Requested plan: PRO.",
                "Subscription sync: FAILED.",
                "Payment lookup: NOT_FOUND.",
            ],
        },
        reason=(
            "The unresolved billing/subscription mismatch needs specialist "
            "support."
        ),
        issue_type=(
            "subscription_upgrade_payment_unverified"
        ),
    )


def _refund_recommendation() -> ActionRecommendation:
    return ActionRecommendation(
        action_name="request_refund_review",
        arguments={
            "customer_id": "CUS-1002",
            "payment_id": "PAY-3002",
            "reason": (
                "Customer explicitly requested a refund after payment "
                "verification."
            ),
        },
        reason=(
            "A human refund review is appropriate; no refund is automatic."
        ),
        issue_type="refund_request",
    )


def _approve(
    db,
    proposal_id: str,
) -> None:
    approve_action(
        db,
        proposal_id,
        ApprovalDecisionInput(
            decided_by="support-operator"
        ),
    )


def _prepare_retry_state(
    db,
) -> Subscription:
    subscription = db.scalar(
        select(Subscription).where(
            Subscription.customer_id
            == "CUS-1007"
        )
    )

    assert subscription is not None

    subscription.plan = "BASIC"
    subscription.requested_plan = "PRO"
    subscription.last_sync_status = "FAILED"

    payment = db.get(
        Payment,
        "PAY-3007",
    )

    assert payment is not None

    payment.customer_id = "CUS-1007"
    payment.plan = "PRO"
    payment.status = "SUCCESS"

    db.flush()

    return subscription


def test_unexpected_retry_failure_rolls_back_partial_account_change(
    monkeypatch,
) -> None:
    with SessionLocal() as db:
        subscription = _prepare_retry_state(
            db
        )

        conversation, run = _context(
            db,
            "CUS-1007",
            issue_type="subscription_upgrade_failure",
        )

        proposal = create_action_proposal(
            db,
            conversation_id=conversation.conversation_id,
            run_id=run.run_id,
            customer_id="CUS-1007",
            recommendation=_retry_recommendation(),
        )
        _approve(
            db,
            proposal.proposal_id,
        )

        def broken_retry(
            action_db,
            payload,
        ):
            current = action_db.scalar(
                select(Subscription).where(
                    Subscription.customer_id
                    == payload.customer_id
                )
            )

            assert current is not None

            current.plan = payload.requested_plan
            current.last_sync_status = "SUCCESS"
            action_db.flush()

            raise RuntimeError(
                "Synthetic subscription dependency failure."
            )

        monkeypatch.setattr(
            action_service,
            "retry_subscription_sync",
            broken_retry,
        )

        execution = execute_approved_action(
            db,
            proposal.proposal_id,
        )

        db.expire_all()

        restored = db.scalar(
            select(Subscription).where(
                Subscription.customer_id
                == "CUS-1007"
            )
        )

        assert restored is not None
        assert restored.plan == "BASIC"
        assert restored.last_sync_status == "FAILED"

        assert execution.execution_status == "FAILED"
        assert execution.verification_status == "FAILED"
        assert "RuntimeError" in execution.error

        result = json.loads(
            execution.result_json
        )

        assert (
            result["business_write_committed"]
            is False
        )
        assert (
            result["safe_rollback_applied"]
            is True
        )

        snapshot = build_customer_case_snapshot(
            db,
            conversation,
        )

        assert (
            snapshot["case_status"]
            == "NEEDS_SUPPORT"
        )
        assert (
            "could not be completed safely"
            in snapshot["message"].lower()
        )

        db.rollback()


def test_unexpected_ticket_failure_does_not_leave_partial_ticket(
    monkeypatch,
) -> None:
    with SessionLocal() as db:
        conversation, run = _context(
            db,
            "CUS-1005",
            issue_type=(
                "subscription_upgrade_payment_unverified"
            ),
        )

        proposal = create_action_proposal(
            db,
            conversation_id=conversation.conversation_id,
            run_id=run.run_id,
            customer_id="CUS-1005",
            recommendation=_ticket_recommendation(),
        )
        _approve(
            db,
            proposal.proposal_id,
        )

        def broken_ticket(
            action_db,
            payload,
            *,
            conversation_id,
            run_id,
            proposal_id,
        ):
            ticket = SupportTicket(
                ticket_number="TKT-SYNTHETICFAIL",
                customer_id=payload.customer_id,
                conversation_id=conversation_id,
                run_id=run_id,
                proposal_id=proposal_id,
                issue_type=payload.issue_type,
                priority=payload.priority,
                summary=payload.summary,
                evidence_json=json.dumps(
                    payload.evidence
                ),
                status="OPEN",
            )

            action_db.add(
                ticket
            )
            action_db.flush()

            raise RuntimeError(
                "Synthetic ticket service failure."
            )

        monkeypatch.setattr(
            action_service,
            "create_support_ticket",
            broken_ticket,
        )

        execution = execute_approved_action(
            db,
            proposal.proposal_id,
        )

        ticket = db.scalar(
            select(SupportTicket).where(
                SupportTicket.proposal_id
                == proposal.proposal_id
            )
        )

        assert ticket is None
        assert execution.execution_status == "FAILED"
        assert execution.verification_status == "FAILED"

        result = json.loads(
            execution.result_json
        )

        assert (
            result["business_write_committed"]
            is False
        )

        db.rollback()


def test_refund_review_stale_payment_is_skipped_without_creating_review() -> None:
    with SessionLocal() as db:
        payment = db.get(
            Payment,
            "PAY-3002",
        )

        assert payment is not None

        payment.customer_id = "CUS-1002"
        payment.status = "SUCCESS"
        db.flush()

        conversation, run = _context(
            db,
            "CUS-1002",
            issue_type="refund_request",
        )

        proposal = create_action_proposal(
            db,
            conversation_id=conversation.conversation_id,
            run_id=run.run_id,
            customer_id="CUS-1002",
            recommendation=_refund_recommendation(),
        )
        _approve(
            db,
            proposal.proposal_id,
        )

        # The external business state changed after human approval.
        payment.status = "REFUNDED"
        db.flush()

        execution = execute_approved_action(
            db,
            proposal.proposal_id,
        )

        review = db.scalar(
            select(RefundReview).where(
                RefundReview.proposal_id
                == proposal.proposal_id
            )
        )

        assert execution.execution_status == "SKIPPED"
        assert execution.verification_status == "FAILED"
        assert review is None

        db.expire(
            payment
        )
        refreshed_payment = db.get(
            Payment,
            "PAY-3002",
        )

        assert refreshed_payment is not None
        assert refreshed_payment.status == "REFUNDED"

        result = json.loads(
            execution.result_json
        )

        assert (
            result["business_write_committed"]
            is False
        )
        assert (
            result["safe_rollback_applied"]
            is True
        )

        db.rollback()


def test_post_action_verification_failure_rolls_back_unverified_write(
    monkeypatch,
) -> None:
    with SessionLocal() as db:
        _prepare_retry_state(
            db
        )

        conversation, run = _context(
            db,
            "CUS-1007",
            issue_type="subscription_upgrade_failure",
        )

        proposal = create_action_proposal(
            db,
            conversation_id=conversation.conversation_id,
            run_id=run.run_id,
            customer_id="CUS-1007",
            recommendation=_retry_recommendation(),
        )
        _approve(
            db,
            proposal.proposal_id,
        )

        def unverified_retry(
            action_db,
            payload,
        ):
            current = action_db.scalar(
                select(Subscription).where(
                    Subscription.customer_id
                    == payload.customer_id
                )
            )

            assert current is not None

            before = {
                "plan": current.plan,
                "last_sync_status":
                    current.last_sync_status,
            }

            current.plan = payload.requested_plan
            current.last_sync_status = "SUCCESS"
            action_db.flush()

            return ControlledActionResult(
                execution_status="SUCCEEDED",
                verification_status="FAILED",
                before_state=before,
                result={
                    "action":
                        "retry_subscription_sync",
                },
                after_state={
                    "plan": "PRO",
                    "last_sync_status": "SUCCESS",
                },
                verification_result={
                    "plan_matches_requested": False,
                    "sync_successful": False,
                },
                error="Synthetic verification failure.",
            )

        monkeypatch.setattr(
            action_service,
            "retry_subscription_sync",
            unverified_retry,
        )

        execution = execute_approved_action(
            db,
            proposal.proposal_id,
        )

        db.expire_all()

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

        # The attempted action said SUCCEEDED, but SupportPilot refused to
        # commit an unverified write and therefore records the final execution
        # as FAILED.
        assert execution.execution_status == "FAILED"
        assert execution.verification_status == "FAILED"

        result = json.loads(
            execution.result_json
        )

        assert (
            result["attempted_execution_status"]
            == "SUCCEEDED"
        )
        assert (
            result["business_write_committed"]
            is False
        )
        assert (
            result["safe_rollback_applied"]
            is True
        )

        db.rollback()


def test_failed_execution_does_not_block_fresh_followup_proposal(
    monkeypatch,
) -> None:
    with SessionLocal() as db:
        _prepare_retry_state(
            db
        )

        conversation, first_run = _context(
            db,
            "CUS-1007",
            issue_type="subscription_upgrade_failure",
        )

        first_proposal = create_action_proposal(
            db,
            conversation_id=conversation.conversation_id,
            run_id=first_run.run_id,
            customer_id="CUS-1007",
            recommendation=_retry_recommendation(),
        )
        _approve(
            db,
            first_proposal.proposal_id,
        )

        def broken_retry(
            action_db,
            payload,
        ):
            raise RuntimeError(
                "Synthetic transient action failure."
            )

        monkeypatch.setattr(
            action_service,
            "retry_subscription_sync",
            broken_retry,
        )

        failed_execution = execute_approved_action(
            db,
            first_proposal.proposal_id,
        )

        assert (
            failed_execution.execution_status
            == "FAILED"
        )

        second_run = AgentRun(
            conversation_id=conversation.conversation_id,
            resolution_status="ESCALATION_REQUIRED",
            issue_type="subscription_upgrade_failure",
            resolution_summary=(
                "Fresh follow-up investigation after failed action."
            ),
        )
        db.add(
            second_run
        )
        db.flush()

        second_proposal = create_action_proposal(
            db,
            conversation_id=conversation.conversation_id,
            run_id=second_run.run_id,
            customer_id="CUS-1007",
            recommendation=_retry_recommendation(),
        )

        assert (
            second_proposal.proposal_id
            != first_proposal.proposal_id
        )
        assert (
            second_proposal.approval_status
            == "PENDING_APPROVAL"
        )

        db.rollback()
