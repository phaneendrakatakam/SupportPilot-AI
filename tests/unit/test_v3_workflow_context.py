from app.agent.orchestrator import (
    _guard_customer_response_for_action_workflow,
)


def test_refund_pending_followup_guard_uses_existing_workflow() -> None:
    result = (
        _guard_customer_response_for_action_workflow(
            model_response=(
                "Please contact billing support."
            ),
            customer_message=(
                "What happens next with my refund?"
            ),
            workflow_context={
                "action_name":
                    "request_refund_review",
                "stage":
                    "PENDING_APPROVAL",
                "summary":
                    "Waiting for human approval.",
            },
        )
    )

    assert (
        "already waiting for human approval"
        in result
    )
    assert (
        "No refund will be issued automatically."
        in result
    )
    assert (
        "contact billing"
        not in result.lower()
    )


def test_payment_followup_is_not_overridden_by_refund_workflow_guard() -> None:
    model_response = (
        "Yes. Your verified payment status is SUCCESS."
    )

    result = (
        _guard_customer_response_for_action_workflow(
            model_response=(
                model_response
            ),
            customer_message=(
                "Was my payment actually successful?"
            ),
            workflow_context={
                "action_name":
                    "request_refund_review",
                "stage":
                    "PENDING_APPROVAL",
                "summary":
                    "Waiting for human approval.",
            },
        )
    )

    assert result == model_response
