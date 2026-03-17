"""
Alerts API Endpoints
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Alert
from app.schemas import AlertResponse, AlertAcknowledgeRequest
from app.core.enums import AlertSeverity

router = APIRouter()


@router.get("/", response_model=List[AlertResponse])
async def list_alerts(
    severity: Optional[AlertSeverity] = None,
    acknowledged: Optional[bool] = None,
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db)
):
    """List alerts with optional filters"""
    query = select(Alert).order_by(Alert.timestamp.desc()).limit(limit)

    if severity:
        query = query.where(Alert.severity == severity)
    if acknowledged is not None:
        query = query.where(Alert.acknowledged == acknowledged)

    result = await db.execute(query)
    alerts = result.scalars().all()

    return [AlertResponse.model_validate(a) for a in alerts]


@router.get("/active", response_model=List[AlertResponse])
async def get_active_alerts(db: AsyncSession = Depends(get_db)):
    """Get all unacknowledged, unresolved alerts"""
    result = await db.execute(
        select(Alert)
        .where(Alert.acknowledged == False)
        .where(Alert.resolved == False)
        .order_by(Alert.severity.desc(), Alert.timestamp.desc())
    )
    alerts = result.scalars().all()
    return [AlertResponse.model_validate(a) for a in alerts]


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: UUID,
    request: AlertAcknowledgeRequest,
    db: AsyncSession = Depends(get_db)
):
    """Acknowledge an alert"""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.acknowledged = True
    alert.acknowledged_at = datetime.utcnow()
    alert.acknowledged_by = request.acknowledged_by

    await db.commit()

    return {"status": "acknowledged", "alert_id": str(alert_id)}


@router.post("/{alert_id}/resolve")
async def resolve_alert(alert_id: UUID, db: AsyncSession = Depends(get_db)):
    """Mark an alert as resolved"""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.resolved = True
    alert.resolved_at = datetime.utcnow()

    await db.commit()

    return {"status": "resolved", "alert_id": str(alert_id)}
