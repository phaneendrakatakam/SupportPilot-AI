import pytest
from pydantic import ValidationError

from app.actions.schemas import (
    ActionLifecycleState,
    ActionRecommendation,
    ApprovalDecisionInput,
    CreateSupportTicketInput,
    RequestRefundReviewInput,
    RetrySubscriptionSyncInput,
)


def test_retry_subscription_sync_input_is_strict() -> None:
    value = RetrySubscriptionSyncInput(
        customer_id="CUS-1007",
        requested_plan="PRO",
    )

    assert value.customer_id == "CUS-1007"
    assert value.requested_plan == "PRO"

    with pytest.raises(ValidationError):
        RetrySubscriptionSyncInput(
            customer_id="CUS-1007",
            requested_plan="PRO",
            force=True,
        )


def test_support_ticket_requires_verified_evidence() -> None:
    value = CreateSupportTicketInput(
        customer_id="CUS-1007",
        issue_type="subscription_upgrade_failure",
        summary="Payment succeeded but subscription synchronization failed.",
        evidence=["Payment SUCCESS", "Subscription sync FAILED"],
    )

    assert value.priority == "HIGH"
    assert len(value.evidence) == 2

    with pytest.raises(ValidationError):
        CreateSupportTicketInput(
            customer_id="CUS-1007",
            issue_type="subscription_upgrade_failure",
            summary="No evidence supplied.",
            evidence=[],
        )


def test_support_ticket_rejects_unknown_priority() -> None:
    with pytest.raises(ValidationError):
        CreateSupportTicketInput(
            customer_id="CUS-1007",
            issue_type="subscription_upgrade_failure",
            summary="Escalation required.",
            priority="CRITICAL",
            evidence=["Subscription sync FAILED"],
        )


def test_refund_review_requires_payment_id() -> None:
    value = RequestRefundReviewInput(
        customer_id="CUS-1002",
        payment_id="PAY-3002",
        reason="Customer requested a refund review.",
    )

    assert value.payment_id == "PAY-3002"

    with pytest.raises(ValidationError):
        RequestRefundReviewInput(
            customer_id="CUS-1002",
            payment_id="",
            reason="Customer requested a refund review.",
        )


def test_action_recommendation_only_allows_v3_actions() -> None:
    value = ActionRecommendation(
        action_name="retry_subscription_sync",
        arguments={
            "customer_id": "CUS-1007",
            "requested_plan": "PRO",
        },
        reason="Successful Pro payment with failed subscription sync.",
        issue_type="subscription_upgrade_failure",
    )

    assert value.action_name == "retry_subscription_sync"

    with pytest.raises(ValidationError):
        ActionRecommendation(
            action_name="delete_customer",
            arguments={"customer_id": "CUS-1007"},
            reason="Unsafe action.",
            issue_type="test",
        )


def test_all_v3_recommendations_require_approval() -> None:
    with pytest.raises(ValidationError):
        ActionRecommendation(
            action_name="create_support_ticket",
            arguments={
                "customer_id": "CUS-1007",
                "issue_type": "subscription_upgrade_failure",
                "summary": "Escalate the issue.",
                "evidence": ["Subscription sync FAILED"],
            },
            reason="Escalation is required.",
            issue_type="subscription_upgrade_failure",
            approval_required=False,
        )


def test_approval_decision_requires_operator_identity() -> None:
    assert ApprovalDecisionInput(decided_by="support-operator").decided_by == (
        "support-operator"
    )

    with pytest.raises(ValidationError):
        ApprovalDecisionInput(decided_by="")


def test_action_lifecycle_rejects_unknown_status() -> None:
    state = ActionLifecycleState(
        approval_status="APPROVED",
        execution_status="SUCCEEDED",
        verification_status="VERIFIED",
    )

    assert state.verification_status == "VERIFIED"

    with pytest.raises(ValidationError):
        ActionLifecycleState(
            approval_status="AUTO_APPROVED",
        )
