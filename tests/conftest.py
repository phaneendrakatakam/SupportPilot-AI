import pytest

from app.db.schema import ensure_schema
from app.db.seed import seed_data


@pytest.fixture(scope="session", autouse=True)
def prepare_database() -> None:
    ensure_schema()
    seed_data()
