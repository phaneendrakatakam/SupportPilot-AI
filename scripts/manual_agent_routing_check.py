from app.agent.orchestrator import run_agent


CASES = [
    {
        "name": "Subscription routing",
        "customer_id": "CUS-1007",
        "message": (
            "What subscription plan "
            "am I currently on?"
        ),
        "expected_tool": (
            "get_subscription"
        ),
    },
    {
        "name": "Customer routing",
        "customer_id": "CUS-1003",
        "message": (
            "Is my customer account active?"
        ),
        "expected_tool": (
            "get_customer"
        ),
    },
    {
        "name": "Service-status routing",
        "customer_id": None,
        "message": (
            "Is the CloudDesk core "
            "service currently down "
            "in the EU region?"
        ),
        "expected_tool": (
            "get_service_status"
        ),
    },
    {
        "name": "Knowledge routing",
        "customer_id": None,
        "message": (
            "What is CloudDesk's "
            "refund policy?"
        ),
        "expected_tool": (
            "search_knowledge_base"
        ),
    },
]


def tools_called(
    trace: list[dict],
) -> list[str]:
    return [
        event["tool"]
        for event in trace
        if event.get("type")
        == "tool_call"
    ]


def main() -> None:
    failures = 0

    print(
        "\n"
        "========================================"
    )
    print(
        "SupportPilot V1 Routing Check"
    )
    print(
        "========================================"
    )

    for index, case in enumerate(
        CASES,
        start=1,
    ):
        print(
            f"\nCASE {index}: "
            f"{case['name']}"
        )

        print(
            f"Message: {case['message']}"
        )

        result = run_agent(
            message=case["message"],
            customer_id=(
                case["customer_id"]
            ),
        )

        called = tools_called(
            result["trace"]
        )

        print(
            f"Expected tool: "
            f"{case['expected_tool']}"
        )

        print(
            f"Tools called: {called}"
        )

        print(
            f"Intent: "
            f"{result['intent']}"
        )

        print(
            f"Conversation ID: "
            f"{result['conversation_id']}"
        )

        print(
            f"Run ID: "
            f"{result['run_id']}"
        )

        print(
            "Response:"
        )

        print(
            result["response"]
        )

        if (
            case["expected_tool"]
            not in called
        ):
            failures += 1

            print(
                "RESULT: FAILED"
            )

        else:
            print(
                "RESULT: PASSED"
            )

    print(
        "\n"
        "========================================"
    )

    if failures:
        raise SystemExit(
            f"{failures} routing "
            "case(s) failed."
        )

    print(
        "ALL FOUR V1 ROUTING "
        "CASES PASSED."
    )


if __name__ == "__main__":
    main()