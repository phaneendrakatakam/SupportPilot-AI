from __future__ import annotations

import json
from pathlib import Path

from app.actions.recommendations import (
    derive_action_recommendation,
)
from app.agent.resolution import (
    derive_resolution,
    guard_customer_response,
    reconcile_resolution_with_model_response,
)


ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = (
    ROOT
    / "tests"
    / "evaluation"
    / "v3_cases.json"
)


def evaluate_case(
    case: dict,
) -> tuple[bool, list[str]]:
    errors: list[str] = []

    resolution = derive_resolution(
        case["trace"]
    )

    if resolution is None:
        return (
            False,
            ["No resolution was produced."],
        )

    model_response = case.get(
        "model_response",
        (
            "I changed the account and completed the requested action."
            if case["expected_resolution_status"]
            != "RESOLVED"
            else resolution.summary
        ),
    )

    resolution = (
        reconcile_resolution_with_model_response(
            resolution,
            model_response,
        )
    )

    if resolution is None:
        return (
            False,
            ["Resolution reconciliation returned None."],
        )

    if (
        resolution.resolution_status
        != case["expected_resolution_status"]
    ):
        errors.append(
            "resolution_status: "
            f'{resolution.resolution_status} '
            "!= "
            f'{case["expected_resolution_status"]}'
        )

    if (
        resolution.issue_type
        != case["expected_issue_type"]
    ):
        errors.append(
            "issue_type: "
            f'{resolution.issue_type} '
            "!= "
            f'{case["expected_issue_type"]}'
        )

    recommendation = derive_action_recommendation(
        resolution,
        case["trace"],
        case.get(
            "customer_message"
        ),
    )

    actual_action = (
        recommendation.action_name
        if recommendation is not None
        else None
    )

    if (
        actual_action
        != case.get(
            "expected_action"
        )
    ):
        errors.append(
            "action: "
            f"{actual_action} "
            "!= "
            f'{case.get("expected_action")}'
        )

    if (
        recommendation is not None
        and case.get(
            "expected_action_customer_id"
        )
        and recommendation.arguments.get(
            "customer_id"
        )
        != case["expected_action_customer_id"]
    ):
        errors.append(
            "action customer_id mismatch."
        )

    guarded = guard_customer_response(
        model_response,
        resolution,
        case.get(
            "customer_message"
        ),
    ).lower()

    for expected_text in case.get(
        "response_contains",
        [],
    ):
        if expected_text.lower() not in guarded:
            errors.append(
                "customer response missing: "
                + expected_text
            )

    for forbidden_text in case.get(
        "response_not_contains",
        [],
    ):
        if forbidden_text.lower() in guarded:
            errors.append(
                "customer response contains forbidden text: "
                + forbidden_text
            )

    return (
        len(errors) == 0,
        errors,
    )


def main() -> int:
    with DATASET_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        cases = json.load(
            file
        )

    passed = 0

    print(
        "SupportPilot AI V3 Formal Evaluation"
    )
    print(
        "=" * 64
    )

    for case in cases:
        ok, errors = evaluate_case(
            case
        )

        status = (
            "PASS"
            if ok
            else "FAIL"
        )

        print(
            f'{status:4}  {case["id"]}  {case["name"]}'
        )

        if ok:
            passed += 1
        else:
            for error in errors:
                print(
                    f"      - {error}"
                )

    total = len(
        cases
    )

    print(
        "-" * 64
    )
    print(
        f"Result: {passed}/{total} passed"
    )

    if passed == total:
        print(
            "Formal V3 evaluation: PASS"
        )
        return 0

    print(
        "Formal V3 evaluation: FAIL"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
