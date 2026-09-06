from app.db.models import Base


V3_TABLES = {
    "action_proposals",
    "action_executions",
    "support_tickets",
    "refund_reviews",
}


def test_v3_action_tables_are_registered_in_metadata() -> None:
    assert V3_TABLES.issubset(set(Base.metadata.tables))


def test_action_proposal_links_to_v2_audit_context() -> None:
    table = Base.metadata.tables["action_proposals"]

    conversation_targets = {
        key.target_fullname
        for key in table.c.conversation_id.foreign_keys
    }
    run_targets = {
        key.target_fullname
        for key in table.c.run_id.foreign_keys
    }
    customer_targets = {
        key.target_fullname
        for key in table.c.customer_id.foreign_keys
    }

    assert conversation_targets == {"conversations.conversation_id"}
    assert run_targets == {"agent_runs.run_id"}
    assert customer_targets == {"customers.customer_id"}
    assert table.c.idempotency_key.unique is True


def test_one_execution_business_object_per_action_proposal() -> None:
    execution = Base.metadata.tables["action_executions"]
    ticket = Base.metadata.tables["support_tickets"]
    refund_review = Base.metadata.tables["refund_reviews"]

    assert execution.c.proposal_id.unique is True
    assert ticket.c.proposal_id.unique is True
    assert refund_review.c.proposal_id.unique is True

    refund_payment_targets = {
        key.target_fullname
        for key in refund_review.c.payment_id.foreign_keys
    }
    assert refund_payment_targets == {"payments.payment_id"}
