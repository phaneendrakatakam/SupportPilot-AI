from app.agent.orchestrator import run_agent


def get_tool_events(
    trace: list[dict],
) -> list[dict]:
    return [
        event
        for event in trace
        if event.get("type") == "tool_call"
    ]


def case_missing_customer_id() -> bool:
    print()
    print(
        "CASE 1: Missing customer ID"
    )

    result = run_agent(
        message=(
            "What subscription plan "
            "am I currently on?"
        ),
        customer_id=None,
    )

    tool_events = get_tool_events(
        result["trace"]
    )

    response_lower = (
        result["response"].lower()
    )

    no_tool_called = (
        len(tool_events) == 0
    )

    asks_for_customer_id = (
        "customer id" in response_lower
        or "customer_id" in response_lower
    )

    print(
        f"Tools called: "
        f"{[event['tool'] for event in tool_events]}"
    )

    print(
        f"Response: {result['response']}"
    )

    passed = (
        no_tool_called
        and asks_for_customer_id
    )

    print(
        "RESULT:",
        "PASSED" if passed else "FAILED",
    )

    return passed


def case_invalid_customer_id() -> bool:
    print()
    print(
        "CASE 2: Invalid customer ID"
    )

    result = run_agent(
        message=(
            "What subscription plan "
            "am I currently on?"
        ),
        customer_id="CUS-9999",
    )

    tool_events = get_tool_events(
        result["trace"]
    )

    subscription_events = [
        event
        for event in tool_events
        if event.get("tool")
        == "get_subscription"
    ]

    tool_called = (
        len(subscription_events) > 0
    )

    if subscription_events:
        tool_result = (
            subscription_events[0]
            .get("result", {})
        )
    else:
        tool_result = {}

    status = str(
        tool_result.get(
            "status",
            ""
        )
    ).upper()

    not_success = (
        status != "SUCCESS"
    )

    print(
        f"Tools called: "
        f"{[event['tool'] for event in tool_events]}"
    )

    print(
        f"Tool status: {status}"
    )

    print(
        f"Response: {result['response']}"
    )

    passed = (
        tool_called
        and not_success
    )

    print(
        "RESULT:",
        "PASSED" if passed else "FAILED",
    )

    return passed


def case_unrelated_request() -> bool:
    print()
    print(
        "CASE 3: Unsupported request"
    )

    result = run_agent(
        message=(
            "Who will win the next "
            "cricket World Cup?"
        ),
        customer_id=None,
    )

    tool_events = get_tool_events(
        result["trace"]
    )

    response_lower = (
        result["response"].lower()
    )

    no_tool_called = (
        len(tool_events) == 0
    )

    scope_response = any(
        phrase in response_lower
        for phrase in [
            "clouddesk",
            "support",
            "outside",
            "scope",
            "can't help",
            "cannot help",
        ]
    )

    print(
        f"Tools called: "
        f"{[event['tool'] for event in tool_events]}"
    )

    print(
        f"Response: {result['response']}"
    )

    passed = (
        no_tool_called
        and scope_response
    )

    print(
        "RESULT:",
        "PASSED" if passed else "FAILED",
    )

    return passed


def main() -> None:
    print()
    print(
        "========================================"
    )
    print(
        "SupportPilot V1 Guardrail Check"
    )
    print(
        "========================================"
    )

    results = [
        case_missing_customer_id(),
        case_invalid_customer_id(),
        case_unrelated_request(),
    ]

    print()
    print(
        "========================================"
    )

    passed_count = sum(
        1
        for result in results
        if result
    )

    print(
        f"PASSED: {passed_count}/3"
    )

    if not all(results):
        raise SystemExit(
            "One or more V1 guardrail "
            "checks failed."
        )

    print(
        "ALL V1 GUARDRAIL CHECKS PASSED."
    )


if __name__ == "__main__":
    main()