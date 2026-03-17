"""Clinical Validation API"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from app.core.database import get_db
from app.services.clinical_validation import (
    ValidationSession,
    ValidationObservation,
    calculate_validation_metrics,
    match_observations_to_system,
)

router = APIRouter()


class CreateSessionRequest(BaseModel):
    case_id: str
    observer_name: str
    notes: Optional[str] = None


class CreateObservationRequest(BaseModel):
    session_id: str
    timestamp: datetime
    event_type: str
    observed_compliant: bool
    staff_id: Optional[str] = None
    notes: Optional[str] = None


@router.post("/sessions")
async def create_session(request: CreateSessionRequest, db: AsyncSession = Depends(get_db)):
    """Create a new validation session"""
    session = ValidationSession(
        case_id=request.case_id,
        observer_name=request.observer_name,
        notes=request.notes,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {"id": session.id, "case_id": session.case_id, "observer_name": session.observer_name}


@router.post("/observations")
async def add_observation(request: CreateObservationRequest, db: AsyncSession = Depends(get_db)):
    """Add an observation to a validation session"""
    obs = ValidationObservation(
        session_id=request.session_id,
        timestamp=request.timestamp,
        event_type=request.event_type,
        observed_compliant=request.observed_compliant,
        staff_id=request.staff_id,
        notes=request.notes,
    )
    db.add(obs)
    await db.commit()
    await db.refresh(obs)
    return {"id": obs.id, "session_id": obs.session_id}


@router.post("/sessions/{session_id}/match")
async def match_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Match observer observations against system-detected events.

    Finds the closest system EntryExitEvent for each unmatched observation
    within a 30-second time window. Populates system_compliant field so
    metrics can be calculated afterwards.
    """
    result = await match_observations_to_system(session_id, db)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/sessions/{session_id}/metrics")
async def get_metrics(session_id: str, db: AsyncSession = Depends(get_db)):
    """Calculate validation metrics for a session"""
    metrics = await calculate_validation_metrics(session_id, db)
    return metrics
