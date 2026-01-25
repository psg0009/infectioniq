"""
Staff API Endpoints
"""

from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Staff
from app.schemas import StaffCreate, StaffUpdate, StaffResponse

router = APIRouter()


@router.get("/", response_model=List[StaffResponse])
async def list_staff(db: AsyncSession = Depends(get_db)):
    """List all staff members"""
    result = await db.execute(select(Staff).where(Staff.is_active == True))
    staff = result.scalars().all()
    return [StaffResponse.model_validate(s) for s in staff]


@router.get("/{staff_id}", response_model=StaffResponse)
async def get_staff(staff_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get staff member by ID"""
    result = await db.execute(select(Staff).where(Staff.id == staff_id))
    staff = result.scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")
    return StaffResponse.model_validate(staff)


@router.post("/", response_model=StaffResponse)
async def create_staff(staff_data: StaffCreate, db: AsyncSession = Depends(get_db)):
    """Create a new staff member"""
    staff = Staff(**staff_data.model_dump())
    db.add(staff)
    await db.commit()
    await db.refresh(staff)
    return StaffResponse.model_validate(staff)
