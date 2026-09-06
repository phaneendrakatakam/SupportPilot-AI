from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_v3_customer_ui_is_customer_focused() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "How can we help?" in response.text
    assert "Popular help" in response.text
    assert "Current case" in response.text
    assert "SupportPilot AI · V3 customer experience" in response.text

    # Internal human controls belong only on /operations.
    assert "Approve action" not in response.text
    assert "Execute approved action" not in response.text
    assert "PENDING_APPROVAL" not in response.text


def test_v3_customer_javascript_uses_customer_safe_case_status() -> None:
    response = client.get("/static/app.js")

    assert response.status_code == 200

    text = response.text

    assert "/api/v1/support/chat" in text
    assert "/case-status" in text
    assert "/api/v1/actions/" not in text
    assert "activeActionProposalId" not in text

    assert "showRetryResolved" in text
    assert "showTicketCreated" in text
    assert "showRefundReviewCreated" in text


def test_v3_customer_styles_are_available() -> None:
    response = client.get("/static/styles.css")

    assert response.status_code == 200
    assert ".customer-summary" in response.text
    assert ".case-card.review" in response.text
    assert ".case-mode-resolved" in response.text



def test_v3_generic_needs_support_uses_customer_safe_snapshot_copy() -> None:
    response = client.get("/static/app.js")

    assert response.status_code == 200

    text = response.text

    assert '=== "GENERAL_REVIEW"' in text
    assert "snapshot.title" in text
    assert "snapshot.message" in text
    # app.js intentionally splits this customer-safe sentence across
    # adjacent JavaScript string literals for readability. Assert the two
    # source fragments rather than requiring one contiguous source string.
    assert (
        "The issue remains open and no unsupported "
        in text
    )
    assert (
        "account change was made."
        in text
    )


def test_customer_ui_can_surface_pending_rejection_handoff_message() -> None:
    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "snapshot.customer_message" in response.text
    assert "appendCustomerCaseOutcomeMessage" in response.text
    assert "human-reviewed support step" in response.text


def test_v3_customer_desktop_keeps_composer_in_viewport() -> None:
    html = client.get("/")
    styles = client.get("/static/styles.css")

    assert html.status_code == 200
    assert styles.status_code == 200

    assert (
        "/static/styles.css?v=20260904-v3-viewport-composer-1"
        in html.text
    )

    text = styles.text

    assert "@media (min-width: 851px)" in text
    assert "height: 100svh;" in text
    assert "overflow: hidden;" in text
    assert ".chat {" in text
    assert "overflow-y: auto;" in text
    assert "scrollbar-gutter: stable;" in text
    assert ".composer-zone {" in text
