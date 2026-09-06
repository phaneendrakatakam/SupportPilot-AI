from app.actions.recommendations import derive_action_recommendation
from app.agent.schemas import ResolutionDecision


def event(tool: str, result: dict) -> dict:
    return {
        "step": 1,
        "type": "tool_call",
        "tool": tool,
        "arguments": {},
        "result_status": result.get("status", "ERROR"),
        "result": result,
    }


def test_upgrade_failure_recommends_subscription_retry() -> None:
    resolution = ResolutionDecision(
        resolution_status="ESCALATION_REQUIRED",
        issue_type="subscription_upgrade_failure",
        summary="Paid upgrade was not applied.",
        evidence=[
            "Payment status: SUCCESS.",
            "Subscription sync status: FAILED.",
        ],
    )

    recommendation = derive_action_recommendation(
        resolution,
        [
            event(
                "get_subscription",
                {
                    "status": "SUCCESS",
                    "customer_id": "CUS-1007",
                    "plan": "BASIC",
                    "requested_plan": "PRO",
                    "last_sync_status": "FAILED",
                },
            ),
            event(
                "get_payment_status",
                {
                    "status": "SUCCESS",
                    "customer_id": "CUS-1007",
                    "payment_id": "PAY-3007",
                    "plan": "PRO",
                    "payment_status": "SUCCESS",
                },
            ),
        ],
        customer_message=(
            "I paid for Pro but my account still shows Basic."
        ),
    )

    assert recommendation is not None
    assert recommendation.action_name == "retry_subscription_sync"
    assert recommendation.arguments == {
        "customer_id": "CUS-1007",
        "requested_plan": "PRO",
    }


def test_explicit_refund_request_recommends_refund_review() -> None:
    resolution = ResolutionDecision(
        resolution_status="RESOLVED",
        issue_type="payment_status_verified",
        summary="Payment was verified.",
        evidence=["Payment status: SUCCESS."],
    )

    recommendation = derive_action_recommendation(
        resolution,
        [
            event(
                "get_payment_status",
                {
                    "status": "SUCCESS",
                    "customer_id": "CUS-1002",
                    "payment_id": "PAY-3002",
                    "plan": "PRO",
                    "payment_status": "SUCCESS",
                },
            ),
        ],
        customer_message=(
            "I want a refund for that payment."
        ),
    )

    assert recommendation is not None
    assert recommendation.action_name == "request_refund_review"
    assert recommendation.arguments["payment_id"] == "PAY-3002"


def test_generic_escalation_recommends_support_ticket() -> None:
    resolution = ResolutionDecision(
        resolution_status="ESCALATION_REQUIRED",
        issue_type="cross_system_plan_conflict",
        summary="Payment and subscription plan evidence conflicts.",
        evidence=["Payment plan: BASIC.", "Requested plan: PRO."],
    )

    recommendation = derive_action_recommendation(
        resolution,
        [
            event(
                "get_subscription",
                {
                    "status": "SUCCESS",
                    "customer_id": "CUS-1007",
                    "plan": "BASIC",
                    "requested_plan": "PRO",
                },
            ),
        ],
    )

    assert recommendation is not None
    assert recommendation.action_name == "create_support_ticket"
    assert recommendation.arguments["customer_id"] == "CUS-1007"


def test_unresolved_pending_payment_does_not_propose_action() -> None:
    resolution = ResolutionDecision(
        resolution_status="UNRESOLVED",
        issue_type="payment_pending",
        summary="Payment is pending.",
        evidence=["Payment status: PENDING."],
    )

    recommendation = derive_action_recommendation(
        resolution,
        [
            event(
                "get_payment_status",
                {
                    "status": "SUCCESS",
                    "customer_id": "CUS-1004",
                    "payment_id": "PAY-3004",
                    "plan": "PRO",
                    "payment_status": "PENDING",
                },
            ),
        ],
    )

    assert recommendation is None



def test_failed_upgrade_with_missing_payment_recommends_support_ticket() -> None:
    resolution = ResolutionDecision(
        resolution_status="UNRESOLVED",
        issue_type="payment_evidence_unavailable",
        summary=(
            "Payment evidence was not available, so the subscription issue "
            "could not be resolved reliably."
        ),
        evidence=[
            "Payment lookup did not return SUCCESS.",
        ],
    )

    recommendation = derive_action_recommendation(
        resolution,
        [
            event(
                "get_subscription",
                {
                    "status": "SUCCESS",
                    "customer_id": "CUS-1005",
                    "plan": "BASIC",
                    "requested_plan": "PRO",
                    "last_sync_status": "FAILED",
                },
            ),
            event(
                "get_payment_status",
                {
                    "status": "NOT_FOUND",
                    "customer_id": "CUS-1005",
                    "error": (
                        "No matching payment record was found for this customer."
                    ),
                },
            ),
        ],
        customer_message=(
            "I upgraded to Pro but my account is still showing Basic. "
            "Can you fix this?"
        ),
    )

    assert recommendation is not None
    assert recommendation.action_name == "create_support_ticket"
    assert recommendation.issue_type == "subscription_upgrade_payment_unverified"
    assert recommendation.arguments["customer_id"] == "CUS-1005"
    assert recommendation.arguments["priority"] == "HIGH"
    assert (
        "Payment lookup status: NOT_FOUND."
        in recommendation.arguments["evidence"]
    )


def test_missing_payment_without_failed_requested_upgrade_does_not_auto_ticket() -> None:
    resolution = ResolutionDecision(
        resolution_status="UNRESOLVED",
        issue_type="payment_evidence_unavailable",
        summary="Payment evidence was not available.",
        evidence=[
            "Payment lookup did not return SUCCESS.",
        ],
    )

    recommendation = derive_action_recommendation(
        resolution,
        [
            event(
                "get_subscription",
                {
                    "status": "SUCCESS",
                    "customer_id": "CUS-1005",
                    "plan": "BASIC",
                    "requested_plan": None,
                    "last_sync_status": "SUCCESS",
                },
            ),
            event(
                "get_payment_status",
                {
                    "status": "NOT_FOUND",
                    "customer_id": "CUS-1005",
                },
            ),
        ],
    )

    assert recommendation is None
