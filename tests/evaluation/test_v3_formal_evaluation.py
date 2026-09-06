import json
from pathlib import Path

import pytest

from app.actions.recommendations import (
    derive_action_recommendation,
)
from app.agent.resolution import (
    derive_resolution,
    guard_customer_response,
    reconcile_resolution_with_model_response,
)


DATASET_PATH = (
    Path(__file__).with_name(
        "v3_cases.json"
    )
)


with DATASET_PATH.open(
    "r",
    encoding="utf-8",
) as file:
    CASES = json.load(
        file
    )


def _case_id(case: dict) -> str:
    return (
        f'{case["id"]}-'
        f'{case["name"]}'
    )


@pytest.mark.parametrize(
    "case",
    CASES,
    ids=_case_id,
)
def test_v3_formal_evaluation_case(
    case: dict,
) -> None:
    resolution = derive_resolution(
        case["trace"]
    )

    assert resolution is not None

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

    assert resolution is not None

    assert (
        resolution.resolution_status
        == case["expected_resolution_status"]
    )
    assert (
        resolution.issue_type
        == case["expected_issue_type"]
    )

    recommendation = derive_action_recommendation(
        resolution,
        case["trace"],
        case.get(
            "customer_message"
        ),
    )

    expected_action = case.get(
        "expected_action"
    )

    if expected_action is None:
        assert recommendation is None

    else:
        assert recommendation is not None
        assert (
            recommendation.action_name
            == expected_action
        )

        expected_customer_id = case.get(
            "expected_action_customer_id"
        )

        if expected_customer_id:
            assert (
                recommendation.arguments[
                    "customer_id"
                ]
                == expected_customer_id
            )

        # Formal V3 safety invariant:
        # recommendation never means approval/execution.
        assert recommendation.action_name in {
            "retry_subscription_sync",
            "create_support_ticket",
            "request_refund_review",
        }

    guarded = guard_customer_response(
        model_response,
        resolution,
        case.get(
            "customer_message"
        ),
    )

    normalized = guarded.lower()

    for expected_text in case.get(
        "response_contains",
        [],
    ):
        assert (
            expected_text.lower()
            in normalized
        )

    for forbidden_text in case.get(
        "response_not_contains",
        [],
    ):
        assert (
            forbidden_text.lower()
            not in normalized
        )
