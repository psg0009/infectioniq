"""
FHIR R4 API Endpoints - EMR/EHR Integration
"""

from datetime import datetime
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.database import get_db
from app.models import SurgicalCase, Staff, RiskScore, Alert, EntryExitEvent

router = APIRouter()


def _fhir_procedure(case: SurgicalCase) -> dict:
    """Convert SurgicalCase to FHIR Procedure resource"""
    status_map = {"SCHEDULED": "preparation", "IN_PROGRESS": "in-progress", "COMPLETED": "completed", "CANCELLED": "not-done"}
    return {
        "resourceType": "Procedure",
        "id": str(case.id),
        "status": status_map.get(case.status.value, "unknown"),
        "code": {
            "coding": [{"system": "http://snomed.info/sct", "display": case.procedure_type}],
            "text": case.procedure_type,
        },
        "subject": {"reference": f"Patient/{case.patient_id}"} if case.patient_id else None,
        "performedPeriod": {
            "start": case.start_time.isoformat() if case.start_time else None,
            "end": case.end_time.isoformat() if case.end_time else None,
        },
        "location": {"display": case.or_number},
        "performer": [{"actor": {"reference": f"Practitioner/{case.surgeon_id}"}}] if case.surgeon_id else [],
    }


def _fhir_practitioner(staff: Staff) -> dict:
    """Convert Staff to FHIR Practitioner resource"""
    return {
        "resourceType": "Practitioner",
        "id": str(staff.id),
        "active": staff.is_active,
        "name": [{"text": staff.name}],
        "identifier": [{"system": "http://infectioniq.local/employee", "value": staff.employee_id}],
        "qualification": [{"code": {"text": staff.role.value}}],
    }


def _fhir_risk_assessment(case: SurgicalCase) -> dict:
    """Convert RiskScore to FHIR RiskAssessment resource"""
    rs = case.risk_score
    return {
        "resourceType": "RiskAssessment",
        "id": str(case.id),
        "status": "final",
        "subject": {"reference": f"Patient/{case.patient_id}"} if case.patient_id else None,
        "basis": [{"reference": f"Procedure/{case.id}"}],
        "prediction": [{
            "outcome": {"text": f"Surgical site infection risk: {rs.risk_level.value}"},
            "probabilityDecimal": rs.score / 100,
            "qualitativeRisk": {"text": rs.risk_level.value},
        }] if rs else [],
        "note": [{"text": ", ".join(f.get("name", "") for f in rs.factors)}] if rs and rs.factors else [],
    }


@router.get("/metadata")
async def capability_statement():
    """FHIR CapabilityStatement (conformance)"""
    return {
        "resourceType": "CapabilityStatement",
        "status": "active",
        "date": datetime.utcnow().isoformat(),
        "kind": "instance",
        "software": {"name": settings.APP_NAME, "version": settings.APP_VERSION},
        "fhirVersion": "4.0.1",
        "format": ["json"],
        "rest": [{
            "mode": "server",
            "resource": [
                {"type": "Procedure", "interaction": [{"code": "read"}]},
                {"type": "Practitioner", "interaction": [{"code": "read"}]},
                {"type": "RiskAssessment", "interaction": [{"code": "read"}]},
                {"type": "Observation", "interaction": [{"code": "search-type"}]},
            ],
        }],
    }


@router.get("/Procedure/{case_id}")
async def get_procedure(case_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get case as FHIR Procedure"""
    result = await db.execute(select(SurgicalCase).where(SurgicalCase.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Procedure not found")
    return _fhir_procedure(case)


@router.get("/Practitioner/{staff_id}")
async def get_practitioner(staff_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get staff as FHIR Practitioner"""
    result = await db.execute(select(Staff).where(Staff.id == staff_id))
    staff = result.scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="Practitioner not found")
    return _fhir_practitioner(staff)


@router.get("/RiskAssessment/{case_id}")
async def get_risk_assessment(case_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get risk score as FHIR RiskAssessment"""
    result = await db.execute(
        select(SurgicalCase).options(selectinload(SurgicalCase.risk_score)).where(SurgicalCase.id == case_id)
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="RiskAssessment not found")
    return _fhir_risk_assessment(case)


@router.get("/Observation")
async def search_observations(case: Optional[UUID] = None, db: AsyncSession = Depends(get_db)):
    """Get compliance data as FHIR Observations"""
    if not case:
        raise HTTPException(status_code=400, detail="case parameter required")

    result = await db.execute(
        select(EntryExitEvent).where(EntryExitEvent.case_id == case).where(EntryExitEvent.event_type == "ENTRY")
    )
    entries = result.scalars().all()

    observations = []
    for entry in entries:
        observations.append({
            "resourceType": "Observation",
            "id": str(entry.id),
            "status": "final",
            "code": {"coding": [{"system": "http://infectioniq.local", "code": "hand-hygiene", "display": "Hand Hygiene Compliance"}]},
            "subject": {"reference": f"Procedure/{entry.case_id}"},
            "effectiveDateTime": entry.timestamp.isoformat(),
            "valueBoolean": entry.compliant,
        })

    return {"resourceType": "Bundle", "type": "searchset", "total": len(observations), "entry": [{"resource": o} for o in observations]}
