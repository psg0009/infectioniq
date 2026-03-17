"""
Compliance Report Generator
=============================
Generates weekly/monthly PDF and HTML compliance reports for hospital pilots.

Used for:
  - Pilot deliverables (show value to infection-control teams)
  - Regulatory documentation
  - Board/admin presentations

Usage:
  POST /api/v1/reports/generate  →  triggers async generation
  GET  /api/v1/reports/{id}/download  →  returns PDF/HTML file
"""

import io
import json
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

from sqlalchemy import select, func, and_, case as sql_case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    SurgicalCase, EntryExitEvent, TouchEvent, Alert, Staff, RiskScore,
)

logger = logging.getLogger(__name__)


@dataclass
class ComplianceMetrics:
    """Aggregated compliance metrics for a report period."""
    period_start: str
    period_end: str
    total_entries: int = 0
    compliant_entries: int = 0
    compliance_rate: float = 0.0
    total_cases: int = 0
    total_alerts: int = 0
    critical_alerts: int = 0
    resolved_alerts: int = 0
    avg_risk_score: float = 0.0
    total_touch_events: int = 0
    contamination_events: int = 0
    or_breakdown: Dict[str, Any] = field(default_factory=dict)
    daily_trend: List[Dict[str, Any]] = field(default_factory=list)
    top_violations: List[Dict[str, Any]] = field(default_factory=list)
    staff_compliance: List[Dict[str, Any]] = field(default_factory=list)


async def gather_metrics(
    db: AsyncSession,
    start_date: datetime,
    end_date: datetime,
    or_numbers: Optional[List[str]] = None,
) -> ComplianceMetrics:
    """Query database and aggregate compliance metrics for the given period."""

    metrics = ComplianceMetrics(
        period_start=start_date.isoformat(),
        period_end=end_date.isoformat(),
    )

    # ── Entry/Exit Compliance ───────────────────────────────────────
    entry_query = select(
        func.count(EntryExitEvent.id).label("total"),
        func.count(EntryExitEvent.id).filter(EntryExitEvent.compliant == True).label("compliant"),
    ).where(
        and_(
            EntryExitEvent.event_type == "ENTRY",
            EntryExitEvent.timestamp >= start_date,
            EntryExitEvent.timestamp <= end_date,
        )
    )
    if or_numbers:
        entry_query = entry_query.where(EntryExitEvent.or_number.in_(or_numbers))

    result = await db.execute(entry_query)
    row = result.first()
    metrics.total_entries = row.total or 0
    metrics.compliant_entries = row.compliant or 0
    metrics.compliance_rate = (
        round(metrics.compliant_entries / metrics.total_entries * 100, 1)
        if metrics.total_entries > 0 else 0.0
    )

    # ── Cases ───────────────────────────────────────────────────────
    case_query = select(func.count(SurgicalCase.id)).where(
        and_(
            SurgicalCase.start_time >= start_date,
            SurgicalCase.start_time <= end_date,
        )
    )
    if or_numbers:
        case_query = case_query.where(SurgicalCase.or_number.in_(or_numbers))
    result = await db.execute(case_query)
    metrics.total_cases = result.scalar() or 0

    # ── Alerts ──────────────────────────────────────────────────────
    alert_query = select(
        func.count(Alert.id).label("total"),
        func.count(Alert.id).filter(Alert.severity == "CRITICAL").label("critical"),
        func.count(Alert.id).filter(Alert.resolved == True).label("resolved"),
    ).where(
        and_(
            Alert.created_at >= start_date,
            Alert.created_at <= end_date,
        )
    )
    if or_numbers:
        alert_query = alert_query.where(Alert.or_number.in_(or_numbers))
    result = await db.execute(alert_query)
    row = result.first()
    metrics.total_alerts = row.total or 0
    metrics.critical_alerts = row.critical or 0
    metrics.resolved_alerts = row.resolved or 0

    # ── Risk Scores ─────────────────────────────────────────────────
    risk_query = select(func.avg(RiskScore.score)).join(
        SurgicalCase, RiskScore.case_id == SurgicalCase.id
    ).where(
        and_(
            SurgicalCase.start_time >= start_date,
            SurgicalCase.start_time <= end_date,
        )
    )
    result = await db.execute(risk_query)
    avg = result.scalar()
    metrics.avg_risk_score = round(float(avg), 1) if avg else 0.0

    # ── Touch Events / Contamination ────────────────────────────────
    touch_query = select(
        func.count(TouchEvent.id).label("total"),
        func.count(TouchEvent.id).filter(
            TouchEvent.person_state_after == "CONTAMINATED"
        ).label("contaminated"),
    ).where(
        and_(
            TouchEvent.timestamp >= start_date,
            TouchEvent.timestamp <= end_date,
        )
    )
    result = await db.execute(touch_query)
    row = result.first()
    metrics.total_touch_events = row.total or 0
    metrics.contamination_events = row.contaminated or 0

    # ── OR Breakdown ────────────────────────────────────────────────
    or_query = select(
        EntryExitEvent.or_number,
        func.count(EntryExitEvent.id).label("total"),
        func.count(EntryExitEvent.id).filter(EntryExitEvent.compliant == True).label("compliant"),
    ).where(
        and_(
            EntryExitEvent.event_type == "ENTRY",
            EntryExitEvent.timestamp >= start_date,
            EntryExitEvent.timestamp <= end_date,
        )
    ).group_by(EntryExitEvent.or_number)
    if or_numbers:
        or_query = or_query.where(EntryExitEvent.or_number.in_(or_numbers))

    result = await db.execute(or_query)
    for row in result.all():
        rate = round(row.compliant / row.total * 100, 1) if row.total > 0 else 0.0
        metrics.or_breakdown[row.or_number] = {
            "total_entries": row.total,
            "compliant_entries": row.compliant,
            "compliance_rate": rate,
        }

    # ── Daily Trend ─────────────────────────────────────────────────
    daily_query = select(
        func.date(EntryExitEvent.timestamp).label("day"),
        func.count(EntryExitEvent.id).label("total"),
        func.count(EntryExitEvent.id).filter(EntryExitEvent.compliant == True).label("compliant"),
    ).where(
        and_(
            EntryExitEvent.event_type == "ENTRY",
            EntryExitEvent.timestamp >= start_date,
            EntryExitEvent.timestamp <= end_date,
        )
    ).group_by(func.date(EntryExitEvent.timestamp)).order_by(func.date(EntryExitEvent.timestamp))

    result = await db.execute(daily_query)
    for row in result.all():
        rate = round(row.compliant / row.total * 100, 1) if row.total > 0 else 0.0
        metrics.daily_trend.append({
            "date": str(row.day),
            "total_entries": row.total,
            "compliant_entries": row.compliant,
            "compliance_rate": rate,
        })

    # ── Staff Compliance ────────────────────────────────────────────
    staff_query = select(
        Staff.name,
        Staff.role,
        func.count(EntryExitEvent.id).label("total"),
        func.count(EntryExitEvent.id).filter(EntryExitEvent.compliant == True).label("compliant"),
    ).join(
        EntryExitEvent, Staff.id == EntryExitEvent.staff_id
    ).where(
        and_(
            EntryExitEvent.event_type == "ENTRY",
            EntryExitEvent.timestamp >= start_date,
            EntryExitEvent.timestamp <= end_date,
        )
    ).group_by(Staff.id, Staff.name, Staff.role).order_by(func.count(EntryExitEvent.id).desc())

    result = await db.execute(staff_query)
    for row in result.all():
        rate = round(row.compliant / row.total * 100, 1) if row.total > 0 else 0.0
        metrics.staff_compliance.append({
            "name": row.name,
            "role": row.role,
            "total_entries": row.total,
            "compliant_entries": row.compliant,
            "compliance_rate": rate,
        })

    return metrics


def generate_html_report(metrics: ComplianceMetrics, title: str = "InfectionIQ Compliance Report") -> str:
    """Generate an HTML compliance report from aggregated metrics."""

    compliance_color = (
        "#22c55e" if metrics.compliance_rate >= 85
        else "#eab308" if metrics.compliance_rate >= 70
        else "#ef4444"
    )

    # OR breakdown rows
    or_rows = ""
    for or_num, data in sorted(metrics.or_breakdown.items()):
        c = "#22c55e" if data["compliance_rate"] >= 85 else "#eab308" if data["compliance_rate"] >= 70 else "#ef4444"
        or_rows += f"""
        <tr>
            <td>{or_num}</td>
            <td>{data['total_entries']}</td>
            <td>{data['compliant_entries']}</td>
            <td style="color:{c};font-weight:bold">{data['compliance_rate']}%</td>
        </tr>"""

    # Staff rows
    staff_rows = ""
    for s in metrics.staff_compliance[:10]:
        c = "#22c55e" if s["compliance_rate"] >= 85 else "#eab308" if s["compliance_rate"] >= 70 else "#ef4444"
        staff_rows += f"""
        <tr>
            <td>{s['name']}</td>
            <td>{s['role']}</td>
            <td>{s['total_entries']}</td>
            <td style="color:{c};font-weight:bold">{s['compliance_rate']}%</td>
        </tr>"""

    # Daily trend for chart (simple bar visualization)
    max_entries = max((d["total_entries"] for d in metrics.daily_trend), default=1)
    trend_bars = ""
    for d in metrics.daily_trend:
        bar_width = int(d["total_entries"] / max_entries * 100) if max_entries > 0 else 0
        comp_width = int(d["compliant_entries"] / max_entries * 100) if max_entries > 0 else 0
        trend_bars += f"""
        <div style="margin-bottom:4px;display:flex;align-items:center;gap:8px">
            <span style="width:80px;font-size:12px;color:#666">{d['date'][-5:]}</span>
            <div style="flex:1;background:#f0f0f0;border-radius:4px;height:20px;position:relative">
                <div style="width:{bar_width}%;height:100%;background:#dbeafe;border-radius:4px;position:absolute"></div>
                <div style="width:{comp_width}%;height:100%;background:#22c55e;border-radius:4px;position:absolute"></div>
            </div>
            <span style="width:45px;text-align:right;font-size:12px">{d['compliance_rate']}%</span>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:#f8fafc; color:#1e293b; }}
        .container {{ max-width:900px; margin:0 auto; padding:40px 24px; }}
        .header {{ text-align:center; margin-bottom:40px; }}
        .header h1 {{ font-size:28px; color:#0f172a; margin-bottom:4px; }}
        .header .period {{ color:#64748b; font-size:14px; }}
        .header .generated {{ color:#94a3b8; font-size:12px; margin-top:4px; }}

        .kpi-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:32px; }}
        .kpi {{ background:white; border-radius:12px; padding:20px; text-align:center; box-shadow:0 1px 3px rgba(0,0,0,0.08); }}
        .kpi .value {{ font-size:32px; font-weight:700; }}
        .kpi .label {{ font-size:12px; color:#64748b; margin-top:4px; text-transform:uppercase; letter-spacing:0.5px; }}

        .section {{ background:white; border-radius:12px; padding:24px; margin-bottom:24px; box-shadow:0 1px 3px rgba(0,0,0,0.08); }}
        .section h2 {{ font-size:18px; margin-bottom:16px; color:#0f172a; }}

        table {{ width:100%; border-collapse:collapse; }}
        th {{ text-align:left; padding:8px 12px; border-bottom:2px solid #e2e8f0; font-size:12px; text-transform:uppercase; color:#64748b; letter-spacing:0.5px; }}
        td {{ padding:8px 12px; border-bottom:1px solid #f1f5f9; font-size:14px; }}

        .footer {{ text-align:center; margin-top:40px; color:#94a3b8; font-size:12px; }}
        .footer a {{ color:#3b82f6; text-decoration:none; }}

        @media print {{
            body {{ background:white; }}
            .container {{ max-width:100%; padding:20px; }}
            .kpi-grid {{ grid-template-columns:repeat(4,1fr); }}
            .section {{ box-shadow:none; border:1px solid #e2e8f0; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
            <div class="period">{metrics.period_start[:10]} — {metrics.period_end[:10]}</div>
            <div class="generated">Generated {datetime.utcnow().strftime('%B %d, %Y at %H:%M UTC')}</div>
        </div>

        <div class="kpi-grid">
            <div class="kpi">
                <div class="value" style="color:{compliance_color}">{metrics.compliance_rate}%</div>
                <div class="label">Compliance Rate</div>
            </div>
            <div class="kpi">
                <div class="value">{metrics.total_entries}</div>
                <div class="label">OR Entries</div>
            </div>
            <div class="kpi">
                <div class="value">{metrics.total_cases}</div>
                <div class="label">Surgical Cases</div>
            </div>
            <div class="kpi">
                <div class="value">{metrics.total_alerts}</div>
                <div class="label">Alerts Generated</div>
            </div>
        </div>

        <div class="kpi-grid" style="grid-template-columns:repeat(3,1fr)">
            <div class="kpi">
                <div class="value" style="color:#ef4444">{metrics.critical_alerts}</div>
                <div class="label">Critical Alerts</div>
            </div>
            <div class="kpi">
                <div class="value">{metrics.contamination_events}</div>
                <div class="label">Contamination Events</div>
            </div>
            <div class="kpi">
                <div class="value">{metrics.avg_risk_score}</div>
                <div class="label">Avg Risk Score</div>
            </div>
        </div>

        <div class="section">
            <h2>Daily Compliance Trend</h2>
            <div style="padding:8px 0">{trend_bars if trend_bars else '<p style="color:#94a3b8">No daily data available</p>'}</div>
            <div style="display:flex;gap:16px;margin-top:8px;font-size:11px;color:#94a3b8">
                <span><span style="display:inline-block;width:12px;height:12px;background:#22c55e;border-radius:2px;vertical-align:middle"></span> Compliant</span>
                <span><span style="display:inline-block;width:12px;height:12px;background:#dbeafe;border-radius:2px;vertical-align:middle"></span> Total</span>
            </div>
        </div>

        <div class="section">
            <h2>Operating Room Breakdown</h2>
            <table>
                <thead><tr><th>OR</th><th>Total Entries</th><th>Compliant</th><th>Rate</th></tr></thead>
                <tbody>{or_rows if or_rows else '<tr><td colspan="4" style="color:#94a3b8">No data</td></tr>'}</tbody>
            </table>
        </div>

        <div class="section">
            <h2>Staff Compliance (Top 10)</h2>
            <table>
                <thead><tr><th>Staff Member</th><th>Role</th><th>Entries</th><th>Rate</th></tr></thead>
                <tbody>{staff_rows if staff_rows else '<tr><td colspan="4" style="color:#94a3b8">No data</td></tr>'}</tbody>
            </table>
        </div>

        <div class="section">
            <h2>Summary</h2>
            <ul style="list-style:none;padding:0">
                <li style="padding:6px 0;border-bottom:1px solid #f1f5f9">
                    <strong>Alert Resolution Rate:</strong>
                    {round(metrics.resolved_alerts / metrics.total_alerts * 100, 1) if metrics.total_alerts > 0 else 0}%
                    ({metrics.resolved_alerts} of {metrics.total_alerts} resolved)
                </li>
                <li style="padding:6px 0;border-bottom:1px solid #f1f5f9">
                    <strong>Contamination Rate:</strong>
                    {round(metrics.contamination_events / metrics.total_touch_events * 100, 1) if metrics.total_touch_events > 0 else 0}%
                    ({metrics.contamination_events} of {metrics.total_touch_events} touch events)
                </li>
                <li style="padding:6px 0">
                    <strong>Average Infection Risk Score:</strong>
                    {metrics.avg_risk_score} / 100
                </li>
            </ul>
        </div>

        <div class="footer">
            <p>Generated by <a href="#">InfectionIQ</a> — AI-powered surgical infection prevention</p>
            <p style="margin-top:4px">This report is for internal hospital quality improvement use only.</p>
        </div>
    </div>
</body>
</html>"""

    return html
