from app.agent.schemas import PaymentLookupInput
from app.db.session import SessionLocal
from app.tools.payment import get_payment_status


def test_latest_payment_for_cus_1007_is_success() -> None:
    with SessionLocal() as db:
        result = get_payment_status(db, PaymentLookupInput(customer_id="CUS-1007"))
    assert result.status == "SUCCESS"
    assert result.payment_id == "PAY-3007"
    assert result.payment_status == "SUCCESS"


def test_specific_failed_payment_lookup_works() -> None:
    with SessionLocal() as db:
        result = get_payment_status(
            db,
            PaymentLookupInput(customer_id="CUS-1001", payment_id="PAY-3001"),
        )
    assert result.status == "SUCCESS"
    assert result.payment_status == "FAILED"


def test_pending_payment_is_preserved() -> None:
    with SessionLocal() as db:
        result = get_payment_status(db, PaymentLookupInput(customer_id="CUS-1004"))
    assert result.status == "SUCCESS"
    assert result.payment_status == "PENDING"


def test_missing_payment_returns_not_found() -> None:
    with SessionLocal() as db:
        result = get_payment_status(db, PaymentLookupInput(customer_id="CUS-1005"))
    assert result.status == "NOT_FOUND"
