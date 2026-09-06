from datetime import (
    datetime,
    timedelta,
    timezone,
)

from sqlalchemy import delete

from app.agent import orchestrator
from app.db.models import (
    Conversation,
    Message,
)
from app.db.session import SessionLocal


def test_v2_has_five_approved_tools() -> None:
    names = {
        declaration.name
        for declaration in (
            orchestrator.V2_TOOL
            .function_declarations
        )
    }

    assert names == {
        "get_customer",
        "get_subscription",
        "get_payment_status",
        "get_service_status",
        "search_knowledge_base",
    }


def test_tool_intent_mapping() -> None:
    assert (
        orchestrator._intent_from_tool(
            "get_payment_status"
        )
        == "payment"
    )


def test_invalid_arguments_are_rejected() -> None:
    result = orchestrator._execute_tool(
        db=None,
        tool_name="get_subscription",
        arguments={},
    )

    assert (
        result["status"]
        == "ERROR"
    )

    assert (
        "Invalid tool arguments"
        in result["error"]
    )


def test_unknown_tool_is_rejected() -> None:
    result = orchestrator._execute_tool(
        db=None,
        tool_name="delete_account",
        arguments={},
    )

    assert (
        result["status"]
        == "ERROR"
    )

    assert (
        "Unsupported tool"
        in result["error"]
    )


def test_recent_context_is_bounded_to_eight_messages() -> None:
    now = datetime.now(
        timezone.utc
    )

    with SessionLocal() as db:
        conversation = Conversation(
            customer_id="CUS-1007"
        )

        db.add(
            conversation
        )

        db.flush()

        conversation_id = (
            conversation.conversation_id
        )

        for index in range(
            12
        ):
            db.add(
                Message(
                    conversation_id=(
                        conversation_id
                    ),
                    role=(
                        "user"
                        if index % 2 == 0
                        else "assistant"
                    ),
                    content=(
                        f"context-{index}"
                    ),
                    created_at=(
                        now
                        + timedelta(
                            seconds=index
                        )
                    ),
                )
            )

        db.commit()

        history = (
            orchestrator
            ._load_recent_conversation_messages(
                db,
                conversation_id,
            )
        )

        contents = [
            item.content
            for item in history
        ]

        assert len(
            history
        ) == 8

        assert contents == [
            f"context-{index}"
            for index in range(
                4,
                12,
            )
        ]

        # Use explicit SQL DELETE statements so PostgreSQL sees the child
        # message rows removed before the parent conversation row. The ORM
        # models intentionally do not define relationship cascades, so
        # db.delete(child) + db.delete(parent) in one flush can violate the
        # messages.conversation_id foreign-key constraint.
        db.execute(
            delete(
                Message
            ).where(
                Message.conversation_id
                == conversation_id
            )
        )

        db.execute(
            delete(
                Conversation
            ).where(
                Conversation.conversation_id
                == conversation_id
            )
        )

        db.commit()
