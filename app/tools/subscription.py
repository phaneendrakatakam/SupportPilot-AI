from sqlalchemy import select
from sqlalchemy.orm import Session
from app.agent.schemas import SubscriptionLookupInput, SubscriptionResult
from app.db.models import Subscription


def get_subscription(db: Session, payload: SubscriptionLookupInput) -> SubscriptionResult:
    subscription = db.scalar(
        select(Subscription).where(Subscription.customer_id == payload.customer_id)
    )
    if subscription is None:
        return SubscriptionResult(
            status="NOT_FOUND",
            customer_id=payload.customer_id,
            error="No subscription record was found for this customer.",
        )
    return SubscriptionResult(
        status="SUCCESS",
        subscription_id=subscription.subscription_id,
        customer_id=subscription.customer_id,
        plan=subscription.plan,
        subscription_status=subscription.status,
        requested_plan=subscription.requested_plan,
        last_sync_status=subscription.last_sync_status,
    )
