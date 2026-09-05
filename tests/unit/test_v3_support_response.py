from app.api.support import ChatResponse


def test_chat_response_accepts_v3_action_proposal() -> None:
    response = ChatResponse(
        response="Verified support response.",
        conversation_id="conversation-1",
        run_id="run-1",
        intent="subscription",
        resolution=None,
        action_proposal={
            "proposal_id": "proposal-1",
            "action_name": "retry_subscription_sync",
            "arguments": {
                "customer_id": "CUS-1007",
                "requested_plan": "PRO",
            },
            "reason": "Paid upgrade has a failed sync.",
            "issue_type": "subscription_upgrade_failure",
            "approval_required": True,
            "approval_status": "PENDING_APPROVAL",
            "proposed_at": None,
        },
        trace=[],
    )

    assert response.action_proposal is not None
    assert (
        response.action_proposal.action_name
        == "retry_subscription_sync"
    )
