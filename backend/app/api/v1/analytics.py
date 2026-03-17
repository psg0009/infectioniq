"""
Analytics API Endpoints
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, Integer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.enums import CaseStatus
from app.models import (
    SurgicalCase, EntryExitEvent, TouchEvent, Alert,
    Dispenser, DispenserStatus
)
from app.schemas import DashboardMetricsResponse

router = APIRouter()


@router.get("/dashboard", response_model=DashboardMetricsResponse)
async def get_dashboard_metrics(db: AsyncSession = Depends(get_db)):
    """Get dashboard overview metrics"""

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # Active cases
    active_result = await db.execute(
        select(func.count(SurgicalCase.id))
        .where(SurgicalCase.status == CaseStatus.IN_PROGRESS)
    )
    active_cases = active_result.scalar() or 0

    # Today's entries
    entries_result = await db.execute(
        select(
            func.count(EntryExitEvent.id).label("total"),
            func.sum(func.cast(EntryExitEvent.compliant, Integer)).label("compliant")
        )
        .where(EntryExitEvent.timestamp >= today_start)
        .where(EntryExitEvent.event_type == "ENTRY")
    )
    entries_data = entries_result.one()
    today_entries = entries_data.total or 0
    today_compliant = entries_data.compliant or 0
    today_violations = today_entries - today_compliant

    # Compliance rate
    compliance_rate = today_compliant / today_entries if today_entries > 0 else 1.0

    # Active alerts
    alerts_result = await db.execute(
        select(func.count(Alert.id))
        .where(Alert.acknowledged == False)
        .where(Alert.resolved == False)
    )
    active_alerts = alerts_result.scalar() or 0

    # Critical alerts
    critical_result = await db.execute(
        select(func.count(Alert.id))
        .where(Alert.acknowledged == False)
        .where(Alert.resolved == False)
        .where(Alert.severity == "CRITICAL")
    )
    critical_alerts = critical_result.scalar() or 0

    # Low dispensers
    dispensers_result = await db.execute(
        select(func.count(DispenserStatus.dispenser_id))
        .where(DispenserStatus.status.in_(["WARNING", "LOW", "CRITICAL", "EMPTY"]))
    )
    dispensers_low = dispensers_result.scalar() or 0

    return DashboardMetricsResponse(
        active_cases=active_cases,
        overall_compliance_rate=compliance_rate,
        active_alerts=active_alerts,
        critical_alerts=critical_alerts,
        dispensers_low=dispensers_low,
        today_entries=today_entries,
        today_violations=today_violations
    )


@router.get("/trends")
async def get_compliance_trends(
    days: int = Query(7, le=90),
    db: AsyncSession = Depends(get_db)
):
    """Get compliance trends over time"""

    start_date = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(
            func.date(EntryExitEvent.timestamp).label("date"),
            func.count(EntryExitEvent.id).label("total"),
            func.sum(func.cast(EntryExitEvent.compliant, Integer)).label("compliant")
        )
        .where(EntryExitEvent.timestamp >= start_date)
        .where(EntryExitEvent.event_type == "ENTRY")
        .group_by(func.date(EntryExitEvent.timestamp))
        .order_by(func.date(EntryExitEvent.timestamp))
    )

    trends = []
    for row in result:
        compliance_rate = row.compliant / row.total if row.total > 0 else 1.0
        date_val = row.date
        trends.append({
            "date": date_val.isoformat() if hasattr(date_val, "isoformat") else str(date_val),
            "compliance_rate": compliance_rate,
            "total_entries": row.total,
            "compliant_entries": row.compliant
        })

    return {"trends": trends, "days": days}


@router.get("/violations")
async def get_top_violations(
    days: int = Query(30, le=90),
    db: AsyncSession = Depends(get_db)
):
    """Get most common violation types"""

    start_date = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(
            Alert.alert_type,
            func.count(Alert.id).label("count")
        )
        .where(Alert.timestamp >= start_date)
        .group_by(Alert.alert_type)
        .order_by(func.count(Alert.id).desc())
    )

    violations = []
    total = 0
    for row in result:
        violations.append({
            "type": row.alert_type.value if hasattr(row.alert_type, 'value') else row.alert_type,
            "count": row.count
        })
        total += row.count

    # Add percentage
    for v in violations:
        v["percentage"] = (v["count"] / total * 100) if total > 0 else 0

    return {"violations": violations, "total": total}
