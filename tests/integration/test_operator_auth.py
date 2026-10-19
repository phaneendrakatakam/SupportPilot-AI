"""Regression coverage for the operator-only surface."""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


PROTECTED = (
    "/operations",
    "/debug",
    "/api/v1/actions",
    "/api/v1/debug/runs/unknown-run",
)


@pytest.mark.parametrize("path", PROTECTED)
def test_protected_routes_reject_anonymous(path):
    with TestClient(app) as client:
        response = client.get(path)
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Basic"


@pytest.mark.parametrize("path", PROTECTED)
def test_protected_routes_reject_invalid_credentials(path):
    with TestClient(app) as client:
        response = client.get(path, auth=("wrong", "wrong"))
    assert response.status_code == 401


@pytest.mark.parametrize("path", ("/operations", "/debug"))
def test_operator_pages_accept_valid_credentials(path):
    with TestClient(app) as client:
        response = client.get(path, auth=("test-operator", "test-password"))
    assert response.status_code == 200


@pytest.mark.parametrize("path", PROTECTED)
def test_missing_operator_configuration_fails_closed(monkeypatch, path):
    monkeypatch.setattr(settings, "operator_username", None)
    monkeypatch.setattr(settings, "operator_password", None)
    with TestClient(app) as client:
        response = client.get(path, auth=("test-operator", "test-password"))
    assert response.status_code == 503


def test_customer_page_remains_public():
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200


def test_static_assets_remain_public():
    with TestClient(app) as client:
        response = client.get("/static/styles.css")
    assert response.status_code == 200


def test_authorized_debug_unknown_run_preserves_not_found():
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/debug/runs/unknown-run",
            auth=("test-operator", "test-password"),
        )
    assert response.status_code == 404
