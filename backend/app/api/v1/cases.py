"""
Cases API Endpoints
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services import CaseService
from app.schemas import (
    CaseCreate, CaseUpdate, CaseResponse, CaseWithRiskResponse,
    CaseComplianceResponse
)

router = APIRouter()


@router.post("/", response_model=CaseWithRiskResponse, status_code=status.HTTP_201_CREATED)
async def create_case(case_data: CaseCreate, db: AsyncSession = Depends(get_db)):
    """Create a new surgical case with risk prediction"""
    service = CaseService(db)
    return await service.create_case(case_data)


@router.get("/active", response_model=List[CaseWithRiskResponse])
async def get_active_cases(db: AsyncSession = Depends(get_db)):
    """Get all active (in progress) surgical cases"""
    service = CaseService(db)
    return await service.get_active_cases()


@router.get("/{case_id}", response_model=CaseWithRiskResponse)
async def get_case(case_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a surgical case by ID"""
    service = CaseService(db)
    case = await service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(case_id: UUID, update_data: CaseUpdate, db: AsyncSession = Depends(get_db)):
    """Update a surgical case"""
    service = CaseService(db)
    case = await service.update_case(case_id, update_data)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.post("/{case_id}/start", response_model=CaseResponse)
async def start_case(case_id: UUID, db: AsyncSession = Depends(get_db)):
    """Start a surgical case (change status to IN_PROGRESS)"""
    service = CaseService(db)
    case = await service.start_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.post("/{case_id}/end", response_model=CaseResponse)
async def end_case(case_id: UUID, outcome: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """End a surgical case"""
    service = CaseService(db)
    case = await service.end_case(case_id, outcome)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.get("/{case_id}/compliance", response_model=CaseComplianceResponse)
async def get_case_compliance(case_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get compliance statistics for a case"""
    service = CaseService(db)
    compliance = await service.get_case_compliance(case_id)
    if not compliance:
        raise HTTPException(status_code=404, detail="Case not found")
    return compliance
