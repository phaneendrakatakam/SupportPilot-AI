from app.agent.resolution import (
    derive_resolution,
    guard_customer_response,
    maximum_steps_resolution,
    reconcile_resolution_with_model_response,
)


def event(tool: str, result: dict) -> dict:
    return {
        "step": 1,
        "type": "tool_call",
        "tool": tool,
        "arguments": {},
        "result_status": result.get("status", "ERROR"),
        "result": result,
    }


def test_missing_customer_needs_information() -> None:
    r = derive_resolution([event("get_customer", {"status": "NOT_FOUND"})])
    assert r.resolution_status == "NEEDS_INFORMATION"


def test_tool_error_is_unresolved() -> None:
    r = derive_resolution([event("get_payment_status", {"status": "ERROR"})])
    assert r.resolution_status == "UNRESOLVED"


def test_pending_payment_is_unresolved() -> None:
    r = derive_resolution([
        event("get_subscription", {
            "status": "SUCCESS", "customer_id": "CUS-1004", "plan": "BASIC",
            "requested_plan": "PRO", "last_sync_status": "PENDING",
        }),
        event("get_payment_status", {
            "status": "SUCCESS", "customer_id": "CUS-1004", "plan": "PRO",
            "payment_status": "PENDING",
        }),
    ])
    assert r.issue_type == "payment_pending"


def test_failed_payment_is_resolved_explanation() -> None:
    r = derive_resolution([
        event("get_subscription", {
            "status": "SUCCESS", "customer_id": "CUS-1001", "plan": "BASIC",
            "requested_plan": "PRO", "last_sync_status": "FAILED",
        }),
        event("get_payment_status", {
            "status": "SUCCESS", "customer_id": "CUS-1001", "plan": "PRO",
            "payment_status": "FAILED",
        }),
    ])
    assert r.resolution_status == "RESOLVED"
    assert r.issue_type == "payment_failure"


def test_upgrade_mismatch_requires_escalation() -> None:
    r = derive_resolution([
        event("get_subscription", {
            "status": "SUCCESS", "customer_id": "CUS-1007", "plan": "BASIC",
            "requested_plan": "PRO", "last_sync_status": "FAILED",
        }),
        event("get_payment_status", {
            "status": "SUCCESS", "customer_id": "CUS-1007", "plan": "PRO",
            "payment_status": "SUCCESS",
        }),
    ])

    assert r.resolution_status == "ESCALATION_REQUIRED"

    follow_up = guard_customer_response(
        model_response="The upgrade failed for an unknown reason.",
        resolution=r,
        customer_message="Why did it fail?",
    )

    assert "synchronization is marked as failed" in follow_up
    assert "underlying technical cause" in follow_up
    assert "I haven't changed the account" in follow_up


def test_successful_upgrade_is_resolved() -> None:
    r = derive_resolution([
        event("get_subscription", {
            "status": "SUCCESS", "customer_id": "CUS-1006", "plan": "PRO",
            "requested_plan": "PRO", "last_sync_status": "SUCCESS",
        }),
        event("get_payment_status", {
            "status": "SUCCESS", "customer_id": "CUS-1006", "plan": "PRO",
            "payment_status": "SUCCESS",
        }),
    ])
    assert r.resolution_status == "RESOLVED"


def test_plan_conflict_requires_escalation() -> None:
    r = derive_resolution([
        event("get_subscription", {
            "status": "SUCCESS", "customer_id": "CUS-1007", "plan": "BASIC",
            "requested_plan": "PRO", "last_sync_status": "FAILED",
        }),
        event("get_payment_status", {
            "status": "SUCCESS", "customer_id": "CUS-1007", "plan": "BASIC",
            "payment_status": "SUCCESS",
        }),
    ])
    assert r.issue_type == "cross_system_plan_conflict"


def test_active_service_incident_is_confirmed() -> None:
    r = derive_resolution([
        event("get_service_status", {
            "status": "SUCCESS",
            "active_incidents": [{"incident_id": "INC-2001", "severity": "SEV2"}],
        })
    ])
    assert r.issue_type == "service_incident_confirmed"


def test_guard_blocks_unsafe_failed_payment_claim() -> None:
    r = derive_resolution([
        event(
            "get_payment_status",
            {
                "status": "ERROR",
            },
        )
    ])

    response = guard_customer_response(
        "Your payment definitely failed.",
        r,
    )

    assert (
        "definitely failed"
        not in response.lower()
    )

    knowledge_resolution = derive_resolution([
        event(
            "search_knowledge_base",
            {
                "status": "SUCCESS",
                "results": [
                    {
                        "content": (
                            "Subscription upgrades normally take effect "
                            "after payment confirmation."
                        ),
                        "source": "subscription_changes.md",
                        "score": 0.61,
                    }
                ],
            },
        )
    ])

    grounded_uncertainty = (
        "The available CloudDesk documentation does not confirm whether "
        "CloudDesk offers a lifetime subscription plan."
    )

    reconciled = (
        reconcile_resolution_with_model_response(
            resolution=knowledge_resolution,
            model_response=grounded_uncertainty,
        )
    )

    assert (
        reconciled.resolution_status
        == "UNRESOLVED"
    )

    assert (
        reconciled.issue_type
        == "knowledge_evidence_unavailable"
    )

    preserved = guard_customer_response(
        model_response=grounded_uncertainty,
        resolution=reconciled,
    )

    assert (
        preserved
        == grounded_uncertainty
    )


def test_maximum_steps_resolution_is_unresolved() -> None:
    r = maximum_steps_resolution()
    assert r.resolution_status == "UNRESOLVED"
    assert r.issue_type == "maximum_steps_reached"
