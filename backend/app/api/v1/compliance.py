"""
Compliance API Endpoints
"""

from typing import Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services import ComplianceService
from app.schemas import (
    EntryEventCreate, TouchEventCreate, 
    TouchEventWithStateResponse
)

router = APIRouter()


@router.post("/entry")
async def record_entry(event_data: EntryEventCreate, db: AsyncSession = Depends(get_db)):
    """Record an OR entry event with compliance status"""
    service = ComplianceService(db)
    return await service.record_entry(event_data)


@router.post("/exit")
async def record_exit(
    case_id: UUID,
    staff_id: Optional[UUID] = None,
    person_track_id: Optional[int] = None,
    timestamp: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db)
):
    """Record an OR exit event"""
    service = ComplianceService(db)
    return await service.record_exit(case_id, staff_id, person_track_id, timestamp)


@router.post("/touch", response_model=TouchEventWithStateResponse)
async def record_touch(event_data: TouchEventCreate, db: AsyncSession = Depends(get_db)):
    """Record a touch event and update contamination state"""
    service = ComplianceService(db)
    return await service.record_touch(event_data)


@router.post("/sanitize")
async def record_sanitize(
    case_id: UUID,
    staff_id: Optional[UUID] = None,
    person_track_id: Optional[int] = None,
    volume_ml: Optional[float] = None,
    duration_sec: Optional[float] = None,
    timestamp: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db)
):
    """Record a sanitization event"""
    service = ComplianceService(db)
    return await service.record_sanitize(
        case_id, staff_id, person_track_id,
        volume_ml, duration_sec, timestamp
    )
