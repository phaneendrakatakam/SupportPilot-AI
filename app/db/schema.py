from sqlalchemy import text

from app.db.models import Base
from app.db.session import engine


AGENT_RUN_ALTERS = [
    "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS request_message TEXT",
    "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS issue_type VARCHAR(120)",
    "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS resolution_summary TEXT",
    "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS final_response TEXT",
    "ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS trace_json TEXT",
]


def ensure_schema() -> None:
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        for statement in AGENT_RUN_ALTERS:
            connection.execute(text(statement))


def reset_schema() -> None:
    Base.metadata.drop_all(bind=engine)
    ensure_schema()
