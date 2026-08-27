from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_support_ui_is_available() -> None:
    response = client.get("/")

    assert response.status_code == 200

    assert (
        "SupportPilot AI"
        in response.text
    )

    assert (
        "Agent Trace"
        in response.text
    )


def test_developer_view_toggle_exists() -> None:
    response = client.get("/")

    assert response.status_code == 200

    assert (
        'id="developer-view-button"'
        in response.text
    )

    assert (
        'aria-expanded="false"'
        in response.text
    )

    assert (
        'id="agent-trace-panel"'
        in response.text
    )

    assert (
        'aria-hidden="true"'
        in response.text
    )


def test_stylesheet_is_available() -> None:
    response = client.get(
        "/static/styles.css"
    )

    assert response.status_code == 200

    assert (
        "--background"
        in response.text
    )

    assert (
        "developer-view-open"
        in response.text
    )


def test_frontend_javascript_is_available() -> None:
    response = client.get(
        "/static/app.js"
    )

    assert response.status_code == 200

    assert (
        "/api/v1/support/chat"
        in response.text
    )

    assert (
        "setDeveloperView"
        in response.text
    )