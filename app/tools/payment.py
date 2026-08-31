from sqlalchemy import select
from sqlalchemy.orm import Session
from app.agent.schemas import PaymentLookupInput, PaymentResult
from app.db.models import Payment


def get_payment_status(db: Session, payload: PaymentLookupInput) -> PaymentResult:
    statement = select(Payment).where(Payment.customer_id == payload.customer_id)

    if payload.payment_id:
        statement = statement.where(Payment.payment_id == payload.payment_id)
    else:
        statement = statement.order_by(
            Payment.payment_date.desc(),
            Payment.payment_id.desc(),
        )

    payment = db.scalar(statement.limit(1))

    if payment is None:
        return PaymentResult(
            status="NOT_FOUND",
            customer_id=payload.customer_id,
            error="No matching payment record was found for this customer.",
        )

    return PaymentResult(
        status="SUCCESS",
        payment_id=payment.payment_id,
        customer_id=payment.customer_id,
        transaction_reference=payment.transaction_reference,
        plan=payment.plan,
        amount=payment.amount,
        currency=payment.currency,
        payment_status=payment.status,
        payment_date=payment.payment_date.isoformat(),
    )
