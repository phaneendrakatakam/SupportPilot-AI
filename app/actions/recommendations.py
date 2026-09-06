from __future__ import annotations

from typing import Any

from app.actions.schemas import ActionRecommendation
from app.agent.schemas import ResolutionDecision


REFUND_REQUEST_TERMS = (
    "refund",
    "money back",
    "reimbursement",
)


def _tool_events(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        event
        for event in trace
        if event.get("type") == "tool_call"
    ]


def _latest_tool_result(
    trace: list[dict[str, Any]],
    tool_name: str,
) -> dict[str, Any] | None:
    for event in reversed(_tool_events(trace)):
        if (
            event.get("tool") == tool_name
            and isinstance(event.get("result"), dict)
        ):
            return event["result"]

    return None


def _is_refund_request(customer_message: str | None) -> bool:
    normalized = (customer_message or "").strip().lower()

    return any(
        term in normalized
        for term in REFUND_REQUEST_TERMS
    )


def _has_failed_requested_upgrade(
    subscription: dict[str, Any] | None,
) -> bool:
    if not subscription:
        return False

    current_plan = subscription.get("plan")
    requested_plan = subscription.get("requested_plan")

    return (
        subscription.get("status") == "SUCCESS"
        and bool(subscription.get("customer_id"))
        and bool(requested_plan)
        and current_plan != requested_plan
        and subscription.get("last_sync_status") == "FAILED"
    )


def _missing_payment_upgrade_ticket_evidence(
    resolution: ResolutionDecision,
    subscription: dict[str, Any],
    payment: dict[str, Any],
) -> list[str]:
    evidence = list(
        resolution.evidence
    )

    verified_items = [
        (
            "Current subscription plan: "
            f"{subscription.get('plan')}."
        ),
        (
            "Requested subscription plan: "
            f"{subscription.get('requested_plan')}."
        ),
        (
            "Subscription sync status: "
            f"{subscription.get('last_sync_status')}."
        ),
        (
            "Payment lookup status: "
            f"{payment.get('status')}."
        ),
    ]

    for item in verified_items:
        if item not in evidence:
            evidence.append(item)

    return evidence


def derive_action_recommendation(
    resolution: ResolutionDecision | None,
    trace: list[dict[str, Any]],
    customer_message: str | None = None,
) -> ActionRecommendation | None:
    """
    Derive one controlled V3 action recommendation from verified V2 evidence.

    This function recommends only. It does not approve or execute actions.
    """

    if resolution is None:
        return None

    subscription = _latest_tool_result(
        trace,
        "get_subscription",
    )
    payment = _latest_tool_result(
        trace,
        "get_payment_status",
    )

    if (
        _is_refund_request(customer_message)
        and payment is not None
        and payment.get("status") == "SUCCESS"
        and payment.get("payment_status") == "SUCCESS"
        and payment.get("payment_id")
        and payment.get("customer_id")
    ):
        return ActionRecommendation(
            action_name="request_refund_review",
            arguments={
                "customer_id": payment["customer_id"],
                "payment_id": payment["payment_id"],
                "reason": (
                    "The customer requested a refund review for a verified "
                    "successful CloudDesk payment."
                ),
            },
            reason=(
                "A successful payment was verified and the customer explicitly "
                "requested a refund review. V3 may create a review request, but "
                "must not issue an automatic refund."
            ),
            issue_type=resolution.issue_type,
        )

    # A requested upgrade with a verified FAILED subscription sync but no
    # matching payment record must not be retried automatically. The payment
    # lookup result is missing evidence, not proof that payment failed. Create
    # a human-review ticket so support can reconcile billing and subscription
    # state without making an unsupported account change.
    if (
        resolution.resolution_status == "UNRESOLVED"
        and resolution.issue_type == "payment_evidence_unavailable"
        and _has_failed_requested_upgrade(subscription)
        and payment is not None
        and payment.get("status") == "NOT_FOUND"
    ):
        return ActionRecommendation(
            action_name="create_support_ticket",
            arguments={
                "customer_id": subscription["customer_id"],
                "issue_type": "subscription_upgrade_payment_unverified",
                "summary": (
                    "The requested subscription upgrade is still not applied "
                    "and the subscription synchronization is FAILED, but no "
                    "matching payment record could be verified. Human support "
                    "must reconcile the billing and subscription state before "
                    "any remediation is attempted."
                ),
                "priority": "HIGH",
                "evidence": (
                    _missing_payment_upgrade_ticket_evidence(
                        resolution,
                        subscription,
                        payment,
                    )
                ),
            },
            reason=(
                "The requested upgrade is stuck in a failed synchronization "
                "state, but the payment system returned no matching payment "
                "record. Retrying the subscription sync would be unsafe, so "
                "the issue requires a structured human support ticket."
            ),
            issue_type="subscription_upgrade_payment_unverified",
        )

    if (
        resolution.resolution_status == "ESCALATION_REQUIRED"
        and resolution.issue_type == "subscription_upgrade_failure"
        and subscription is not None
        and payment is not None
        and subscription.get("status") == "SUCCESS"
        and payment.get("status") == "SUCCESS"
        and payment.get("payment_status") == "SUCCESS"
        and subscription.get("customer_id")
        and subscription.get("requested_plan")
        and payment.get("plan") == subscription.get("requested_plan")
    ):
        return ActionRecommendation(
            action_name="retry_subscription_sync",
            arguments={
                "customer_id": subscription["customer_id"],
                "requested_plan": subscription["requested_plan"],
            },
            reason=(
                "Payment succeeded for the requested plan, but the current "
                "subscription does not match the requested plan and the "
                "synchronization state requires remediation."
            ),
            issue_type=resolution.issue_type,
        )

    if (
        resolution.resolution_status == "ESCALATION_REQUIRED"
        and resolution.issue_type
        not in {
            "customer_identification",
            "payment_pending",
        }
    ):
        customer_id = None

        for result in (
            subscription,
            payment,
            _latest_tool_result(trace, "get_customer"),
        ):
            if result and result.get("customer_id"):
                customer_id = result["customer_id"]
                break

        if customer_id:
            return ActionRecommendation(
                action_name="create_support_ticket",
                arguments={
                    "customer_id": customer_id,
                    "issue_type": resolution.issue_type,
                    "summary": resolution.summary,
                    "priority": "HIGH",
                    "evidence": resolution.evidence,
                },
                reason=(
                    "The investigation requires human support review and no "
                    "safer automated remediation is currently recommended."
                ),
                issue_type=resolution.issue_type,
            )

    return None
