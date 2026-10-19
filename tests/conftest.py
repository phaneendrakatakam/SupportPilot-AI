import pytest

from app.db.schema import ensure_schema
from app.db.seed import seed_data


@pytest.fixture(scope="session", autouse=True)
def prepare_database() -> None:
    ensure_schema()
    seed_data()


@pytest.fixture(scope="session", autouse=True)
def configure_test_operator():
    """Use synthetic operator credentials for integration tests only."""
    from app.config import settings

    old_username = settings.operator_username
    old_password = settings.operator_password
    settings.operator_username = "test-operator"
    settings.operator_password = "test-password"
    try:
        yield
    finally:
        settings.operator_username = old_username
        settings.operator_password = old_password
