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
        "How can we help?"
        in response.text
    )

    assert (
        'id="customer-id"'
        in response.text
    )

    assert (
        'id="chat-form"'
        in response.text
    )


def test_customer_ui_keeps_customer_safe_case_status_and_trust() -> None:
    response = client.get("/")

    assert response.status_code == 200

    text = response.text

    assert (
        'id="status-card"'
        in text
    )

    assert (
        "Current case"
        in text
    )

    assert (
        "Verified support answers"
        in text
    )

    assert (
        "SupportPilot AI · V3 customer experience"
        in text
    )

    # Human approval and execution controls belong on /operations,
    # never on the customer-facing page.
    assert (
        "Approve action"
        not in text
    )

    assert (
        "Execute approved action"
        not in text
    )

    assert (
        "PENDING_APPROVAL"
        not in text
    )


def test_customer_stylesheet_has_v3_customer_layout() -> None:
    response = client.get(
        "/static/styles.css"
    )

    assert (
        response.status_code
        == 200
    )

    text = response.text

    assert (
        ".sidebar"
        in text
    )

    assert (
        ".main"
        in text
    )

    assert (
        ".status-card"
        in text
    )

    assert (
        ".case-card"
        in text
    )

    assert (
        ".customer-summary"
        in text
    )


def test_customer_frontend_javascript_is_available() -> None:
    response = client.get(
        "/static/app.js"
    )

    assert (
        response.status_code
        == 200
    )

    text = response.text

    assert (
        "/api/v1/support/chat"
        in text
    )

    # The V3 customer UI must use the customer-safe conversation
    # case-status endpoint rather than polling internal action APIs.
    assert (
        "/case-status"
        in text
    )

    assert (
        "/api/v1/actions/"
        not in text
    )

    assert (
        "showRetryResolved"
        in text
    )

    assert (
        "showTicketCreated"
        in text
    )

    assert (
        "showRefundReviewCreated"
        in text
    )
