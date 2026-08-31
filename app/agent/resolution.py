from typing import Any

from app.agent.schemas import ResolutionDecision


TOOL_FAILURE_STATES = {"ERROR", "NOT_READY"}

SAFE_CUSTOMER_RESPONSES = {
    "customer_identification": (
        "I couldn't find a matching CloudDesk customer record. "
        "Please provide a valid customer ID so I can continue."
    ),
    "tool_execution_failure": (
        "I couldn't complete the investigation because a required support "
        "system did not return usable information. I don't have enough "
        "verified evidence to determine the outcome yet."
    ),
    "maximum_steps_reached": (
        "I couldn't complete the investigation within the allowed number of "
        "support checks. I don't have enough verified evidence to give you "
        "a reliable conclusion yet."
    ),
    "subscription_evidence_unavailable": (
        "I couldn't verify the subscription state, so I can't safely "
        "determine the outcome of this issue yet."
    ),
    "payment_evidence_unavailable": (
        "I couldn't verify the payment state, so I can't safely determine "
        "the outcome of this issue yet."
    ),
    "payment_pending": (
        "The payment is still pending, so there isn't enough verified "
        "information yet to determine the final subscription outcome."
    ),
    "cross_system_customer_conflict": (
        "I found conflicting customer information between the support systems. "
        "I can't safely determine the correct account state, so this requires "
        "additional support review."
    ),
    "cross_system_plan_conflict": (
        "I found conflicting plan information between the payment and "
        "subscription systems. I can't safely determine the correct "
        "subscription state, so this requires additional support review."
    ),
    "subscription_upgrade_failure": (
        "I verified that the payment for the requested plan succeeded, but the "
        "requested subscription plan is still not applied because the "
        "subscription synchronization is marked as failed. I haven't changed "
        "the account, and this requires additional support review."
    ),
    "service_incident_not_confirmed": (
        "I couldn't confirm an active CloudDesk incident matching the service "
        "and region checked. That does not prove there is no customer-specific "
        "problem, so the issue remains unresolved."
    ),
    "knowledge_evidence_unavailable": (
        "I couldn't find enough verified CloudDesk documentation to answer "
        "that safely."
    ),
    "cross_system_state_unclear": (
        "The available payment and subscription information does not support "
        "a safe conclusion. Additional review is required."
    ),
}


def _tool_events(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event for event in trace if event.get("type") == "tool_call"]


def _latest_tool_result(
    events: list[dict[str, Any]],
    tool_name: str,
) -> dict[str, Any] | None:
    for event in reversed(events):
        if event.get("tool") == tool_name and isinstance(event.get("result"), dict):
            return event["result"]
    return None



def _response_expresses_knowledge_uncertainty(
    model_response: str | None,
) -> bool:
    """
    Detect explicit customer-facing statements that the retrieved CloudDesk
    documentation does not provide enough evidence to confirm a requested
    fact.

    This is deliberately conservative. It is used only to avoid classifying
    a knowledge-only answer as RESOLVED when the final answer itself says the
    documentation is insufficient.
    """

    normalized = (
        model_response
        or ""
    ).strip().lower()

    if not normalized:
        return False

    uncertainty_phrases = (
        "does not provide enough information to confirm",
        "doesn't provide enough information to confirm",
        "do not provide enough information to confirm",
        "not enough information to confirm",
        "does not confirm",
        "doesn't confirm",
        "do not confirm",
        "cannot confirm",
        "can't confirm",
        "could not confirm",
        "couldn't confirm",
        "unable to confirm",
        "does not mention",
        "doesn't mention",
        "not documented",
        "insufficient information",
        "insufficient documentation",
    )

    return any(
        phrase in normalized
        for phrase in uncertainty_phrases
    )


def reconcile_resolution_with_model_response(
    resolution: ResolutionDecision | None,
    model_response: str | None,
) -> ResolutionDecision | None:
    """
    Reconcile a knowledge-only resolution with the model's grounded final
    response.

    Semantic retrieval can return related passages without those passages
    proving the requested fact. If the model explicitly reports that the
    retrieved documentation is insufficient to confirm the answer, the
    structured outcome must remain UNRESOLVED rather than being marked
    RESOLVED merely because retrieval returned candidates.
    """

    if resolution is None:
        return None

    if (
        resolution.resolution_status == "RESOLVED"
        and resolution.issue_type == "knowledge_answer"
        and _response_expresses_knowledge_uncertainty(
            model_response
        )
    ):
        return ResolutionDecision(
            resolution_status="UNRESOLVED",
            issue_type="knowledge_evidence_unavailable",
            summary=(
                "Related CloudDesk documentation was retrieved, but it did "
                "not provide enough evidence to confirm the requested fact."
            ),
            evidence=[
                *resolution.evidence,
                (
                    "The grounded final response explicitly reported that "
                    "the available documentation was insufficient to confirm "
                    "the requested fact."
                ),
            ],
        )

    return resolution


def _is_failure_reason_follow_up(
    customer_message: str | None,
) -> bool:
    """
    Detect a narrow class of conversational follow-ups asking why a
    previously discussed operation failed.

    This is intentionally small and deterministic. It does not try to
    understand arbitrary language; it only lets the safety guard choose a
    more useful approved response for common failure-reason follow-ups.
    """

    normalized = (
        customer_message
        or ""
    ).strip().lower()

    if not normalized:
        return False

    failure_terms = (
        "why did it fail",
        "why did that fail",
        "why did the upgrade fail",
        "why wasn't it upgraded",
        "why was it not upgraded",
        "why didn't it upgrade",
        "why did it not upgrade",
        "what caused it to fail",
        "what caused the failure",
    )

    return any(
        term in normalized
        for term in failure_terms
    )


def guard_customer_response(
    model_response: str,
    resolution: ResolutionDecision | None,
    customer_message: str | None = None,
) -> str:
    cleaned = (
        model_response
        or ""
    ).strip()

    if resolution is None:
        return cleaned

    if resolution.resolution_status == "RESOLVED":
        return (
            cleaned
            or resolution.summary
        )

    if (
        resolution.issue_type
        == "knowledge_evidence_unavailable"
        and _response_expresses_knowledge_uncertainty(
            cleaned
        )
    ):
        return cleaned

    if (
        resolution.issue_type
        == "subscription_upgrade_failure"
        and _is_failure_reason_follow_up(
            customer_message
        )
    ):
        return (
            "The requested Pro upgrade was not applied because the "
            "subscription synchronization is marked as failed. Your payment "
            "for the requested plan succeeded, but the available evidence "
            "does not show the underlying technical cause of the "
            "synchronization failure. I haven't changed the account, and "
            "this requires additional support review."
        )

    return SAFE_CUSTOMER_RESPONSES.get(
        resolution.issue_type,
        resolution.summary,
    )


def maximum_steps_resolution() -> ResolutionDecision:
    return ResolutionDecision(
        resolution_status="UNRESOLVED",
        issue_type="maximum_steps_reached",
        summary=(
            "The investigation reached the configured step limit before "
            "enough evidence was collected for a reliable conclusion."
        ),
        evidence=["Maximum investigation step limit reached."],
    )


def derive_resolution(trace: list[dict[str, Any]]) -> ResolutionDecision | None:
    events = _tool_events(trace)
    if not events:
        return None

    customer = _latest_tool_result(events, "get_customer")
    subscription = _latest_tool_result(events, "get_subscription")
    payment = _latest_tool_result(events, "get_payment_status")
    service = _latest_tool_result(events, "get_service_status")
    knowledge = _latest_tool_result(events, "search_knowledge_base")

    if customer and customer.get("status") == "NOT_FOUND":
        return ResolutionDecision(
            resolution_status="NEEDS_INFORMATION",
            issue_type="customer_identification",
            summary=(
                "The supplied customer record could not be found. A valid "
                "CloudDesk customer ID is required before the issue can be "
                "investigated further."
            ),
            evidence=["Customer lookup returned NOT_FOUND."],
        )

    failed = [
        event for event in events
        if event.get("result_status") in TOOL_FAILURE_STATES
    ]
    if failed:
        return ResolutionDecision(
            resolution_status="UNRESOLVED",
            issue_type="tool_execution_failure",
            summary=(
                "The investigation could not be completed because one or "
                "more required support tools did not return usable evidence."
            ),
            evidence=[
                "Tool failure: " + ", ".join(str(item.get("tool")) for item in failed)
            ],
        )

    if service is not None:
        if service.get("status") != "SUCCESS":
            return ResolutionDecision(
                resolution_status="UNRESOLVED",
                issue_type="tool_execution_failure",
                summary="Service status could not be verified.",
                evidence=["Service status lookup did not return SUCCESS."],
            )

        incidents = service.get("active_incidents") or []
        if incidents:
            first = incidents[0]
            return ResolutionDecision(
                resolution_status="RESOLVED",
                issue_type="service_incident_confirmed",
                summary="An active CloudDesk service incident was confirmed.",
                evidence=[
                    f"Active incident: {first.get('incident_id')}.",
                    f"Incident severity: {first.get('severity')}.",
                ],
            )

        if subscription is None and payment is None:
            return ResolutionDecision(
                resolution_status="UNRESOLVED",
                issue_type="service_incident_not_confirmed",
                summary=(
                    "No active incident matched the service-status check, but "
                    "that alone does not explain the customer's issue."
                ),
                evidence=["Service lookup returned no active matching incidents."],
            )

    if knowledge is not None and subscription is None and payment is None and service is None:
        if knowledge.get("status") == "SUCCESS" and knowledge.get("results"):
            return ResolutionDecision(
                resolution_status="RESOLVED",
                issue_type="knowledge_answer",
                summary=(
                    "Relevant CloudDesk documentation was retrieved for the "
                    "customer's support question."
                ),
                evidence=["Knowledge search returned grounding candidates."],
            )

        return ResolutionDecision(
            resolution_status="UNRESOLVED",
            issue_type="knowledge_evidence_unavailable",
            summary=(
                "The available CloudDesk documentation did not provide enough "
                "verified evidence for a reliable answer."
            ),
            evidence=["Knowledge search did not return usable evidence."],
        )

    if subscription is None and payment is None and customer is not None:
        if customer.get("status") == "SUCCESS":
            return ResolutionDecision(
                resolution_status="RESOLVED",
                issue_type="customer_account_verified",
                summary="The customer account information was successfully verified.",
                evidence=["Customer lookup returned SUCCESS."],
            )

    if subscription is not None and payment is None:
        if subscription.get("status") == "SUCCESS":
            return ResolutionDecision(
                resolution_status="RESOLVED",
                issue_type="subscription_state_verified",
                summary="The customer's current subscription state was verified.",
                evidence=[
                    f"Current subscription plan: {subscription.get('plan')}.",
                    f"Subscription status: {subscription.get('subscription_status')}.",
                ],
            )
        return ResolutionDecision(
            resolution_status="UNRESOLVED",
            issue_type="subscription_evidence_unavailable",
            summary="Subscription evidence was not available.",
            evidence=["Subscription lookup did not return SUCCESS."],
        )

    if payment is not None and subscription is None:
        if payment.get("status") != "SUCCESS":
            return ResolutionDecision(
                resolution_status="UNRESOLVED",
                issue_type="payment_evidence_unavailable",
                summary="Payment evidence was not available.",
                evidence=["Payment lookup did not return SUCCESS."],
            )

        payment_status = payment.get("payment_status")
        if payment_status == "PENDING":
            return ResolutionDecision(
                resolution_status="UNRESOLVED",
                issue_type="payment_pending",
                summary="The payment is still pending.",
                evidence=["Payment status: PENDING."],
            )

        return ResolutionDecision(
            resolution_status="RESOLVED",
            issue_type="payment_status_verified",
            summary="The customer's payment state was successfully verified.",
            evidence=[f"Payment status: {payment_status}."],
        )

    if subscription is None or payment is None:
        return None

    if subscription.get("status") != "SUCCESS":
        return ResolutionDecision(
            resolution_status="UNRESOLVED",
            issue_type="subscription_evidence_unavailable",
            summary=(
                "Subscription evidence was not available, so the billing or "
                "upgrade issue could not be resolved reliably."
            ),
            evidence=["Subscription lookup did not return SUCCESS."],
        )

    if payment.get("status") != "SUCCESS":
        return ResolutionDecision(
            resolution_status="UNRESOLVED",
            issue_type="payment_evidence_unavailable",
            summary=(
                "Payment evidence was not available, so the subscription "
                "issue could not be resolved reliably."
            ),
            evidence=["Payment lookup did not return SUCCESS."],
        )

    sub_customer = subscription.get("customer_id")
    pay_customer = payment.get("customer_id")
    current_plan = subscription.get("plan")
    requested_plan = subscription.get("requested_plan")
    sync_status = subscription.get("last_sync_status")
    payment_plan = payment.get("plan")
    payment_status = payment.get("payment_status")

    evidence = [
        f"Subscription customer ID: {sub_customer}.",
        f"Payment customer ID: {pay_customer}.",
        f"Current subscription plan: {current_plan}.",
        f"Requested subscription plan: {requested_plan}.",
        f"Subscription sync status: {sync_status}.",
        f"Payment plan: {payment_plan}.",
        f"Payment status: {payment_status}.",
    ]

    if sub_customer and pay_customer and sub_customer != pay_customer:
        return ResolutionDecision(
            resolution_status="ESCALATION_REQUIRED",
            issue_type="cross_system_customer_conflict",
            summary=(
                "The subscription and payment systems returned different "
                "customer identifiers."
            ),
            evidence=evidence,
        )

    if payment_status == "PENDING":
        return ResolutionDecision(
            resolution_status="UNRESOLVED",
            issue_type="payment_pending",
            summary="The payment is still pending.",
            evidence=evidence,
        )

    if payment_status == "FAILED":
        return ResolutionDecision(
            resolution_status="RESOLVED",
            issue_type="payment_failure",
            summary=(
                "The payment failed, which explains why the requested paid "
                "plan was not applied."
            ),
            evidence=evidence,
        )

    if payment_status == "REFUNDED":
        return ResolutionDecision(
            resolution_status="RESOLVED",
            issue_type="payment_refunded",
            summary="The investigation found that the payment was refunded.",
            evidence=evidence,
        )

    if payment_status != "SUCCESS":
        return ResolutionDecision(
            resolution_status="UNRESOLVED",
            issue_type="unknown_payment_state",
            summary="The payment state does not support a reliable conclusion.",
            evidence=evidence,
        )

    if requested_plan and payment_plan and payment_plan != requested_plan:
        return ResolutionDecision(
            resolution_status="ESCALATION_REQUIRED",
            issue_type="cross_system_plan_conflict",
            summary=(
                "A successful payment was found, but the payment plan does "
                "not match the requested subscription plan."
            ),
            evidence=evidence,
        )

    if requested_plan and current_plan == requested_plan and sync_status == "SUCCESS":
        return ResolutionDecision(
            resolution_status="RESOLVED",
            issue_type="subscription_upgrade_completed",
            summary=(
                "The payment succeeded and the requested subscription plan is "
                "applied with a successful synchronization state."
            ),
            evidence=evidence,
        )

    if requested_plan and current_plan != requested_plan and payment_plan == requested_plan:
        return ResolutionDecision(
            resolution_status="ESCALATION_REQUIRED",
            issue_type="subscription_upgrade_failure",
            summary=(
                "Payment succeeded for the requested plan, but the current "
                "subscription does not match the requested plan."
            ),
            evidence=evidence,
        )

    if payment_plan and current_plan == payment_plan and sync_status == "SUCCESS":
        return ResolutionDecision(
            resolution_status="RESOLVED",
            issue_type="subscription_payment_consistent",
            summary="The payment and subscription systems show a consistent state.",
            evidence=evidence,
        )

    return ResolutionDecision(
        resolution_status="UNRESOLVED",
        issue_type="cross_system_state_unclear",
        summary=(
            "The available payment and subscription evidence does not map to "
            "a safe deterministic resolution."
        ),
        evidence=evidence,
    )
