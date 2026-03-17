"""
Exportable Reports API - PDF/CSV/HTML generation
"""

import csv
import io
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse, HTMLResponse
from sqlalchemy import select, func, Integer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.enums import CaseStatus
from app.models import SurgicalCase, EntryExitEvent, Alert, Staff
from app.services.report_generator import gather_metrics, generate_html_report

router = APIRouter()


@router.get("/compliance/csv")
async def export_compliance_csv(
    days: int = Query(30, le=365),
    or_number: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Export compliance data as CSV"""
    start_date = datetime.utcnow() - timedelta(days=days)

    query = (
        select(
            EntryExitEvent.timestamp,
            EntryExitEvent.event_type,
            EntryExitEvent.compliant,
            EntryExitEvent.case_id,
            EntryExitEvent.staff_id,
        )
        .where(EntryExitEvent.timestamp >= start_date)
        .order_by(EntryExitEvent.timestamp.desc())
    )

    if or_number:
        query = query.join(SurgicalCase, EntryExitEvent.case_id == SurgicalCase.id).where(
            SurgicalCase.or_number == or_number
        )

    result = await db.execute(query)
    rows = result.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Timestamp", "Event Type", "Compliant", "Case ID", "Staff ID"])
    for row in rows:
        writer.writerow([
            row.timestamp.isoformat() if row.timestamp else "",
            row.event_type,
            row.compliant,
            str(row.case_id),
            str(row.staff_id) if row.staff_id else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=compliance_report_{datetime.utcnow().strftime('%Y%m%d')}.csv"},
    )


@router.get("/cases/csv")
async def export_cases_csv(
    days: int = Query(30, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Export surgical cases as CSV"""
    start_date = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(SurgicalCase)
        .where(SurgicalCase.start_time >= start_date)
        .order_by(SurgicalCase.start_time.desc())
    )
    cases = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "OR Number", "Procedure", "Status", "Start Time", "End Time", "Patient ID"])
    for case in cases:
        writer.writerow([
            str(case.id),
            case.or_number,
            case.procedure_type,
            case.status.value if hasattr(case.status, "value") else case.status,
            case.start_time.isoformat() if case.start_time else "",
            case.end_time.isoformat() if case.end_time else "",
            case.patient_id or "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=cases_report_{datetime.utcnow().strftime('%Y%m%d')}.csv"},
    )


@router.get("/alerts/csv")
async def export_alerts_csv(
    days: int = Query(30, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Export alerts as CSV"""
    start_date = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(Alert)
        .where(Alert.timestamp >= start_date)
        .order_by(Alert.timestamp.desc())
    )
    alerts = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Case ID", "Type", "Severity", "Message", "Timestamp", "Acknowledged", "Resolved"])
    for alert in alerts:
        writer.writerow([
            str(alert.id),
            str(alert.case_id),
            alert.alert_type.value if hasattr(alert.alert_type, "value") else alert.alert_type,
            alert.severity.value if hasattr(alert.severity, "value") else alert.severity,
            alert.message,
            alert.timestamp.isoformat() if alert.timestamp else "",
            alert.acknowledged,
            alert.resolved,
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=alerts_report_{datetime.utcnow().strftime('%Y%m%d')}.csv"},
    )


@router.get("/summary")
async def get_report_summary(
    days: int = Query(30, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get a summary report (JSON) for a given period"""
    start_date = datetime.utcnow() - timedelta(days=days)

    # Case stats
    cases_result = await db.execute(
        select(
            func.count(SurgicalCase.id).label("total"),
            func.sum(func.cast(SurgicalCase.status == CaseStatus.COMPLETED, Integer)).label("completed"),
        )
        .where(SurgicalCase.start_time >= start_date)
    )
    cases_data = cases_result.one()

    # Compliance stats
    compliance_result = await db.execute(
        select(
            func.count(EntryExitEvent.id).label("total"),
            func.sum(func.cast(EntryExitEvent.compliant, Integer)).label("compliant"),
        )
        .where(EntryExitEvent.timestamp >= start_date)
        .where(EntryExitEvent.event_type == "ENTRY")
    )
    compliance_data = compliance_result.one()

    total_entries = compliance_data.total or 0
    compliant_entries = compliance_data.compliant or 0

    # Alert stats
    alerts_result = await db.execute(
        select(func.count(Alert.id)).where(Alert.timestamp >= start_date)
    )
    total_alerts = alerts_result.scalar() or 0

    return {
        "period_days": days,
        "start_date": start_date.isoformat(),
        "end_date": datetime.utcnow().isoformat(),
        "cases": {
            "total": cases_data.total or 0,
            "completed": cases_data.completed or 0,
        },
        "compliance": {
            "total_entries": total_entries,
            "compliant_entries": compliant_entries,
            "rate": compliant_entries / total_entries if total_entries > 0 else 1.0,
        },
        "alerts": {
            "total": total_alerts,
        },
    }


@router.get("/compliance/html")
async def export_compliance_html(
    days: int = Query(7, le=365, description="Report period in days"),
    or_number: Optional[str] = Query(None, description="Filter by OR number"),
    db: AsyncSession = Depends(get_db),
):
    """Generate a full HTML compliance report for the given period.

    Returns a styled, print-ready HTML page with:
    - KPI summary (compliance rate, entries, cases, alerts)
    - Daily compliance trend (bar chart)
    - OR-level breakdown
    - Staff compliance ranking
    - Contamination and risk summary

    Use ?days=7 for weekly, ?days=30 for monthly reports.
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    or_numbers = [or_number] if or_number else None

    metrics = await gather_metrics(db, start_date, end_date, or_numbers)

    period_label = "Weekly" if days <= 7 else "Monthly" if days <= 31 else f"{days}-Day"
    title = f"InfectionIQ {period_label} Compliance Report"
    if or_number:
        title += f" — {or_number}"

    html = generate_html_report(metrics, title=title)
    return HTMLResponse(content=html)


@router.get("/compliance/json")
async def export_compliance_json(
    days: int = Query(7, le=365),
    or_number: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get structured compliance metrics as JSON (for frontend rendering)."""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    or_numbers = [or_number] if or_number else None

    metrics = await gather_metrics(db, start_date, end_date, or_numbers)

    from dataclasses import asdict
    return asdict(metrics)
