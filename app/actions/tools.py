from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.actions.schemas import (
    ControlledActionResult,
    CreateSupportTicketInput,
    RequestRefundReviewInput,
    RetrySubscriptionSyncInput,
)
from app.agent.schemas import SubscriptionLookupInput
from app.db.models import (
    Customer,
    Payment,
    RefundReview,
    Subscription,
    SupportTicket,
)
from app.tools.subscription import get_subscription


def _subscription_state(
    subscription: Subscription,
) -> dict[str, str | None]:
    return {
        "subscription_id": subscription.subscription_id,
        "customer_id": subscription.customer_id,
        "plan": subscription.plan,
        "status": subscription.status,
        "requested_plan": subscription.requested_plan,
        "last_sync_status": subscription.last_sync_status,
    }


def _payment_state(
    payment: Payment,
) -> dict[str, str | None]:
    return {
        "payment_id": payment.payment_id,
        "customer_id": payment.customer_id,
        "plan": payment.plan,
        "status": payment.status,
        "currency": payment.currency,
    }


def _object_number(
    prefix: str,
    proposal_id: str,
) -> str:
    compact = proposal_id.replace("-", "").upper()
    return f"{prefix}-{compact[:12]}"


def retry_subscription_sync(
    db: Session,
    payload: RetrySubscriptionSyncInput,
) -> ControlledActionResult:
    """
    Execute the synthetic V3 subscription-sync remediation.

    The caller is responsible for approval enforcement and transaction commit.
    This function re-checks all required business preconditions before mutation.
    """

    subscription = db.scalar(
        select(Subscription).where(
            Subscription.customer_id
            == payload.customer_id
        )
    )

    if subscription is None:
        return ControlledActionResult(
            execution_status="SKIPPED",
            verification_status="FAILED",
            result={
                "reason": "Subscription record no longer exists.",
            },
            error="Subscription precondition failed.",
        )

    before_state = _subscription_state(
        subscription
    )

    if (
        subscription.plan == payload.requested_plan
        and subscription.last_sync_status == "SUCCESS"
    ):
        return ControlledActionResult(
            execution_status="SKIPPED",
            verification_status="VERIFIED",
            before_state=before_state,
            after_state=before_state,
            result={
                "reason": (
                    "The requested plan is already applied with a successful "
                    "synchronization state. The proposal is stale."
                ),
            },
            verification_result={
                "plan_matches_requested": True,
                "sync_successful": True,
            },
        )

    if subscription.requested_plan != payload.requested_plan:
        return ControlledActionResult(
            execution_status="SKIPPED",
            verification_status="FAILED",
            before_state=before_state,
            after_state=before_state,
            result={
                "reason": (
                    "The subscription's requested plan changed after the "
                    "action proposal was created."
                ),
            },
            error="Stale action proposal.",
        )

    if subscription.last_sync_status != "FAILED":
        return ControlledActionResult(
            execution_status="SKIPPED",
            verification_status="FAILED",
            before_state=before_state,
            after_state=before_state,
            result={
                "reason": (
                    "Subscription synchronization is no longer in FAILED state."
                ),
            },
            error="Stale action proposal.",
        )

    payment = db.scalar(
        select(Payment)
        .where(
            Payment.customer_id
            == payload.customer_id
        )
        .order_by(
            Payment.payment_date.desc(),
            Payment.payment_id.desc(),
        )
        .limit(1)
    )

    if (
        payment is None
        or payment.status != "SUCCESS"
        or payment.plan != payload.requested_plan
    ):
        return ControlledActionResult(
            execution_status="SKIPPED",
            verification_status="FAILED",
            before_state=before_state,
            after_state=before_state,
            result={
                "reason": (
                    "The latest payment evidence no longer supports retrying "
                    "the requested subscription upgrade."
                ),
            },
            error="Payment precondition failed.",
        )

    subscription.plan = payload.requested_plan
    subscription.last_sync_status = "SUCCESS"

    db.flush()
    db.expire(subscription)

    verified = get_subscription(
        db,
        SubscriptionLookupInput(
            customer_id=payload.customer_id
        ),
    )

    verification_ok = (
        verified.status == "SUCCESS"
        and verified.plan == payload.requested_plan
        and verified.last_sync_status == "SUCCESS"
    )

    after_state = {
        "subscription_id": verified.subscription_id,
        "customer_id": verified.customer_id,
        "plan": verified.plan,
        "status": verified.subscription_status,
        "requested_plan": verified.requested_plan,
        "last_sync_status": verified.last_sync_status,
    }

    return ControlledActionResult(
        execution_status="SUCCEEDED",
        verification_status=(
            "VERIFIED"
            if verification_ok
            else "FAILED"
        ),
        before_state=before_state,
        result={
            "action": "retry_subscription_sync",
            "payment_id": payment.payment_id,
            "payment_status": payment.status,
            "requested_plan": payload.requested_plan,
        },
        after_state=after_state,
        verification_result={
            "plan_matches_requested": (
                verified.plan
                == payload.requested_plan
            ),
            "sync_successful": (
                verified.last_sync_status
                == "SUCCESS"
            ),
        },
        error=(
            None
            if verification_ok
            else "Post-action verification failed."
        ),
    )


def create_support_ticket(
    db: Session,
    payload: CreateSupportTicketInput,
    *,
    conversation_id: str,
    run_id: str,
    proposal_id: str,
) -> ControlledActionResult:
    """
    Create and verify one synthetic CloudDesk support ticket.
    """

    customer = db.get(
        Customer,
        payload.customer_id,
    )

    if customer is None:
        return ControlledActionResult(
            execution_status="SKIPPED",
            verification_status="FAILED",
            result={
                "reason": "Customer record no longer exists.",
            },
            error="Customer precondition failed.",
        )

    existing = db.scalar(
        select(SupportTicket).where(
            SupportTicket.proposal_id
            == proposal_id
        )
    )

    if existing is not None:
        state = {
            "ticket_id": existing.ticket_id,
            "ticket_number": existing.ticket_number,
            "status": existing.status,
            "priority": existing.priority,
            "issue_type": existing.issue_type,
        }

        return ControlledActionResult(
            execution_status="SKIPPED",
            verification_status="VERIFIED",
            result={
                "reason": (
                    "A support ticket already exists for this action proposal."
                ),
            },
            after_state=state,
            verification_result={
                "ticket_persisted": True,
                "status": existing.status,
            },
        )

    ticket = SupportTicket(
        ticket_number=_object_number(
            "TKT",
            proposal_id,
        ),
        customer_id=payload.customer_id,
        conversation_id=conversation_id,
        run_id=run_id,
        proposal_id=proposal_id,
        issue_type=payload.issue_type,
        priority=payload.priority,
        summary=payload.summary,
        evidence_json=json.dumps(
            payload.evidence,
            ensure_ascii=False,
        ),
        status="OPEN",
    )

    db.add(ticket)
    db.flush()

    verified = db.get(
        SupportTicket,
        ticket.ticket_id,
    )

    verification_ok = (
        verified is not None
        and verified.proposal_id == proposal_id
        and verified.customer_id == payload.customer_id
        and verified.status == "OPEN"
    )

    after_state = (
        {
            "ticket_id": verified.ticket_id,
            "ticket_number": verified.ticket_number,
            "customer_id": verified.customer_id,
            "issue_type": verified.issue_type,
            "priority": verified.priority,
            "status": verified.status,
        }
        if verified is not None
        else None
    )

    return ControlledActionResult(
        execution_status="SUCCEEDED",
        verification_status=(
            "VERIFIED"
            if verification_ok
            else "FAILED"
        ),
        result={
            "action": "create_support_ticket",
            "ticket_number": (
                verified.ticket_number
                if verified is not None
                else None
            ),
        },
        after_state=after_state,
        verification_result={
            "ticket_persisted": verification_ok,
            "status": (
                verified.status
                if verified is not None
                else None
            ),
        },
        error=(
            None
            if verification_ok
            else "Support-ticket verification failed."
        ),
    )


def request_refund_review(
    db: Session,
    payload: RequestRefundReviewInput,
    *,
    conversation_id: str,
    run_id: str,
    proposal_id: str,
) -> ControlledActionResult:
    """
    Create and verify a human refund-review request.

    This action never changes the Payment record or issues a refund.
    """

    payment = db.get(
        Payment,
        payload.payment_id,
    )

    if (
        payment is None
        or payment.customer_id != payload.customer_id
    ):
        return ControlledActionResult(
            execution_status="SKIPPED",
            verification_status="FAILED",
            result={
                "reason": (
                    "The payment no longer matches the customer in the "
                    "approved action proposal."
                ),
            },
            error="Payment precondition failed.",
        )

    before_payment = _payment_state(
        payment
    )

    if payment.status != "SUCCESS":
        return ControlledActionResult(
            execution_status="SKIPPED",
            verification_status="FAILED",
            before_state=before_payment,
            after_state=before_payment,
            result={
                "reason": (
                    "The payment is no longer in SUCCESS state, so a refund "
                    "review request was not created."
                ),
            },
            error="Stale refund-review proposal.",
        )

    existing = db.scalar(
        select(RefundReview).where(
            RefundReview.proposal_id
            == proposal_id
        )
    )

    if existing is not None:
        return ControlledActionResult(
            execution_status="SKIPPED",
            verification_status="VERIFIED",
            before_state=before_payment,
            after_state={
                **before_payment,
                "review_number": existing.review_number,
                "review_status": existing.status,
            },
            result={
                "reason": (
                    "A refund review already exists for this action proposal."
                ),
            },
            verification_result={
                "review_persisted": True,
                "payment_unchanged": True,
            },
        )

    review = RefundReview(
        review_number=_object_number(
            "RR",
            proposal_id,
        ),
        customer_id=payload.customer_id,
        payment_id=payload.payment_id,
        conversation_id=conversation_id,
        run_id=run_id,
        proposal_id=proposal_id,
        reason=payload.reason,
        status="PENDING_REVIEW",
    )

    db.add(review)
    db.flush()

    verified_review = db.get(
        RefundReview,
        review.refund_review_id,
    )

    db.expire(payment)
    verified_payment = db.get(
        Payment,
        payment.payment_id,
    )

    payment_after = (
        _payment_state(verified_payment)
        if verified_payment is not None
        else None
    )

    payment_unchanged = (
        payment_after == before_payment
    )

    verification_ok = (
        verified_review is not None
        and verified_review.proposal_id == proposal_id
        and verified_review.status == "PENDING_REVIEW"
        and payment_unchanged
    )

    after_state = (
        {
            **payment_after,
            "review_id": verified_review.refund_review_id,
            "review_number": verified_review.review_number,
            "review_status": verified_review.status,
        }
        if (
            payment_after is not None
            and verified_review is not None
        )
        else payment_after
    )

    return ControlledActionResult(
        execution_status="SUCCEEDED",
        verification_status=(
            "VERIFIED"
            if verification_ok
            else "FAILED"
        ),
        before_state=before_payment,
        result={
            "action": "request_refund_review",
            "review_number": (
                verified_review.review_number
                if verified_review is not None
                else None
            ),
        },
        after_state=after_state,
        verification_result={
            "review_persisted": (
                verified_review is not None
            ),
            "review_status": (
                verified_review.status
                if verified_review is not None
                else None
            ),
            "payment_unchanged": payment_unchanged,
        },
        error=(
            None
            if verification_ok
            else "Refund-review verification failed."
        ),
    )
