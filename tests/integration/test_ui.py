from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_customer_ui_is_available() -> None:
    response = client.get("/")

    assert response.status_code == 200

    assert (
        "SupportPilot"
        in response.text
    )

    assert (
        "How can I help today?"
        in response.text
    )


def test_customer_ui_removes_large_explainer_sections() -> None:
    text = client.get("/").text

    assert (
        "SUPPORT CAPABILITIES"
        not in text
    )

    assert (
        "One assistant, multiple support systems."
        not in text
    )

    assert (
        "EVIDENCE FIRST"
        not in text
    )

    assert (
        "Built to avoid confident guesses."
        not in text
    )


def test_customer_ui_keeps_compact_trust_message_and_resolution() -> None:
    text = client.get("/").text

    assert (
        'id="resolution-banner"'
        in text
    )

    assert (
        "won’t guess when evidence is unclear"
        in text
    )

    assert (
        'id="session-state-label"'
        in text
    )


def test_debug_ui_is_separate_and_agent_first() -> None:
    response = client.get(
        "/debug"
    )

    assert response.status_code == 200

    assert (
        "Agent Inspector"
        in response.text
    )

    assert (
        "Tool execution sequence"
        in response.text
    )

    assert (
        'id="run-id-input"'
        in response.text
    )

    assert (
        "no private model chain-of-thought"
        in response.text.lower()
    )


def test_customer_stylesheet_has_board2_layout() -> None:
    response = client.get(
        "/static/styles.css"
    )

    assert (
        response.status_code
        == 200
    )

    assert (
        "inbox-rail"
        in response.text
    )

    assert (
        "conversation-panel"
        in response.text
    )

    assert (
        "trust-line"
        in response.text
    )


def test_customer_frontend_has_safe_markdown() -> None:
    text = client.get(
        "/static/app.js"
    ).text

    assert (
        "renderSafeMarkdown"
        in text
    )

    assert (
        "escapeHtml"
        in text
    )

    assert (
        "bubble.innerHTML"
        in text
    )

    assert (
        "copy-response"
        in text
    )


def test_customer_frontend_has_restoration_without_dev_logic() -> None:
    text = client.get(
        "/static/app.js"
    ).text

    assert (
        "restoreConversation"
        in text
    )

    assert (
        "supportpilot.activeConversationId"
        in text
    )

    assert (
        "/api/v1/support/conversations/"
        in text
    )

    assert (
        "setDeveloperView"
        not in text
    )
