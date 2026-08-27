from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.schemas import (
    ServiceIncidentResult,
    ServiceStatusInput,
    ServiceStatusResult,
)
from app.db.models import ServiceIncident


def get_service_status(db: Session, payload: ServiceStatusInput) -> ServiceStatusResult:
    stmt = select(ServiceIncident).where(
        ServiceIncident.service == payload.service,
        ServiceIncident.status == "ACTIVE",
    )
    if payload.region:
        stmt = stmt.where(ServiceIncident.region == payload.region)

    incidents = list(db.scalars(stmt).all())
    return ServiceStatusResult(
        status="SUCCESS",
        active_incidents=[
            ServiceIncidentResult(
                incident_id=item.incident_id,
                service=item.service,
                region=item.region,
                status=item.status,
                severity=item.severity,
                description=item.description,
            )
            for item in incidents
        ],
    )
