from sqlalchemy import inspect

from app.db.schema import ensure_schema
from app.db.session import engine


def test_v3_tables_exist_in_postgresql_schema() -> None:
    ensure_schema()

    table_names = set(inspect(engine).get_table_names())

    assert {
        "action_proposals",
        "action_executions",
        "support_tickets",
        "refund_reviews",
    }.issubset(table_names)
