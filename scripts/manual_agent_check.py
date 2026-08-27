from app.agent.orchestrator import run_agent


def main() -> None:
    result = run_agent(
        customer_id="CUS-1007",
        message="What subscription plan am I currently on?",
    )

    print("\n=== FINAL RESPONSE ===")
    print(result["response"])

    print("\n=== AGENT TRACE ===")
    for step in result["trace"]:
        print(step)

    tools_called = [
        step["tool"]
        for step in result["trace"]
        if step["type"] == "tool_call"
    ]

    print("\n=== MILESTONE CHECK ===")

    if "get_subscription" not in tools_called:
        raise SystemExit(
            "FAILED: Gemini answered without calling get_subscription()."
        )

    print("PASSED: Gemini correctly called get_subscription().")


if __name__ == "__main__":
    main()