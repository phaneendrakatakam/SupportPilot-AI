from sqlalchemy import select
from sqlalchemy.orm import Session
from app.agent.schemas import ServiceIncidentResult, ServiceStatusInput, ServiceStatusResult
from app.db.models import ServiceIncident


def get_service_status(db: Session, payload: ServiceStatusInput) -> ServiceStatusResult:
    statement = select(ServiceIncident).where(
        ServiceIncident.service == payload.service,
        ServiceIncident.status == "ACTIVE",
    )
    if payload.region:
        statement = statement.where(ServiceIncident.region == payload.region)

    incidents = list(
        db.scalars(statement.order_by(ServiceIncident.started_at.desc())).all()
    )

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
