"""
Consent API Endpoints
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.enums import ConsentType, ConsentStatus
from app.models.consent import PatientConsent

router = APIRouter()


# --- Schemas ---

class ConsentCreate(BaseModel):
    patient_id: str = Field(..., max_length=50)
    case_id: Optional[UUID] = None
    consent_type: ConsentType
    consented_by: str = Field(..., max_length=255)
    witness_name: Optional[str] = None
    witness_id: Optional[UUID] = None
    document_url: Optional[str] = None
    ip_address: Optional[str] = None


class ConsentResponse(BaseModel):
    id: UUID
    patient_id: str
    case_id: Optional[UUID]
    consent_type: ConsentType
    status: ConsentStatus
    consented_by: str
    consented_at: Optional[datetime]
    witness_name: Optional[str]
    revoked_at: Optional[datetime]
    revocation_reason: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ConsentRevokeRequest(BaseModel):
    reason: str


# --- Endpoints ---

@router.post("/", response_model=ConsentResponse, status_code=201)
async def record_consent(data: ConsentCreate, db: AsyncSession = Depends(get_db)):
    """Record a new patient consent"""
    consent = PatientConsent(
        patient_id=data.patient_id,
        case_id=data.case_id,
        consent_type=data.consent_type,
        status=ConsentStatus.GRANTED,
        consented_by=data.consented_by,
        consented_at=datetime.utcnow(),
        witness_name=data.witness_name,
        witness_id=data.witness_id,
        document_url=data.document_url,
        ip_address=data.ip_address,
    )
    db.add(consent)
    await db.commit()
    await db.refresh(consent)
    return consent


@router.get("/patient/{patient_id}", response_model=List[ConsentResponse])
async def get_patient_consents(patient_id: str, db: AsyncSession = Depends(get_db)):
    """Get all consents for a patient"""
    result = await db.execute(
        select(PatientConsent)
        .where(PatientConsent.patient_id == patient_id)
        .order_by(PatientConsent.created_at.desc())
    )
    return result.scalars().all()


@router.get("/patient/{patient_id}/status")
async def check_consent_status(patient_id: str, db: AsyncSession = Depends(get_db)):
    """Check if patient has all required consents"""
    from app.config import settings

    required = settings.CONSENT_REQUIRED_TYPES
    result = await db.execute(
        select(PatientConsent)
        .where(PatientConsent.patient_id == patient_id)
        .where(PatientConsent.status == ConsentStatus.GRANTED)
    )
    granted = {c.consent_type.value for c in result.scalars().all()}
    missing = [t for t in required if t not in granted]

    return {
        "patient_id": patient_id,
        "all_granted": len(missing) == 0,
        "granted": list(granted),
        "missing": missing,
    }


@router.post("/{consent_id}/revoke")
async def revoke_consent(consent_id: UUID, request: ConsentRevokeRequest, db: AsyncSession = Depends(get_db)):
    """Revoke a consent"""
    result = await db.execute(select(PatientConsent).where(PatientConsent.id == consent_id))
    consent = result.scalar_one_or_none()
    if not consent:
        raise HTTPException(status_code=404, detail="Consent not found")

    consent.status = ConsentStatus.REVOKED
    consent.revoked_at = datetime.utcnow()
    consent.revocation_reason = request.reason
    await db.commit()

    return {"status": "revoked", "consent_id": str(consent_id)}


@router.get("/case/{case_id}", response_model=List[ConsentResponse])
async def get_case_consents(case_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get consents for a case"""
    result = await db.execute(
        select(PatientConsent)
        .where(PatientConsent.case_id == case_id)
        .order_by(PatientConsent.created_at.desc())
    )
    return result.scalars().all()
