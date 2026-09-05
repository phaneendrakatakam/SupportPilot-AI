from app.actions.schemas import ApprovalDecisionInput


def test_approval_decision_supports_optional_human_reason() -> None:
    approval = ApprovalDecisionInput(decided_by="support-operator")
    rejection = ApprovalDecisionInput(
        decided_by="support-operator",
        reason="Specialist investigation required",
    )

    assert approval.reason is None
    assert rejection.reason == "Specialist investigation required"
