"""
Dispensers API Endpoints
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Dispenser, DispenserStatus
from app.schemas import DispenserStatusResponse

router = APIRouter()


@router.get("/", response_model=List[DispenserStatusResponse])
async def list_dispensers(db: AsyncSession = Depends(get_db)):
    """List all dispensers with current status"""
    result = await db.execute(
        select(Dispenser, DispenserStatus)
        .join(DispenserStatus, Dispenser.dispenser_id == DispenserStatus.dispenser_id)
    )
    rows = result.all()
    
    return [
        DispenserStatusResponse(
            dispenser_id=disp.dispenser_id,
            or_number=disp.or_number,
            location_description=disp.location_description,
            level_percent=status.level_percent,
            level_ml=status.level_ml,
            status=status.status,
            last_dispense_time=status.last_dispense_time,
            dispenses_today=status.dispenses_today,
            volume_today_ml=status.volume_today_ml or 0,
            estimated_empty_time=status.estimated_empty_time,
            cartridge_expiration_date=status.cartridge_expiration_date,
            days_until_expiration=status.days_until_expiration,
            last_updated=status.last_updated
        )
        for disp, status in rows
    ]


@router.get("/{dispenser_id}/status", response_model=DispenserStatusResponse)
async def get_dispenser_status(dispenser_id: str, db: AsyncSession = Depends(get_db)):
    """Get dispenser status"""
    result = await db.execute(
        select(Dispenser, DispenserStatus)
        .join(DispenserStatus, Dispenser.dispenser_id == DispenserStatus.dispenser_id)
        .where(Dispenser.dispenser_id == dispenser_id)
    )
    row = result.one_or_none()
    
    if not row:
        raise HTTPException(status_code=404, detail="Dispenser not found")
    
    disp, status = row
    return DispenserStatusResponse(
        dispenser_id=disp.dispenser_id,
        or_number=disp.or_number,
        location_description=disp.location_description,
        level_percent=status.level_percent,
        level_ml=status.level_ml,
        status=status.status,
        last_dispense_time=status.last_dispense_time,
        dispenses_today=status.dispenses_today,
        volume_today_ml=status.volume_today_ml or 0,
        estimated_empty_time=status.estimated_empty_time,
        cartridge_expiration_date=status.cartridge_expiration_date,
        days_until_expiration=status.days_until_expiration,
        last_updated=status.last_updated
    )


@router.get("/alerts/active")
async def get_active_dispenser_alerts(db: AsyncSession = Depends(get_db)):
    """Get dispensers that need attention"""
    result = await db.execute(
        select(Dispenser, DispenserStatus)
        .join(DispenserStatus, Dispenser.dispenser_id == DispenserStatus.dispenser_id)
        .where(DispenserStatus.status.in_(["WARNING", "LOW", "CRITICAL", "EMPTY"]))
    )
    rows = result.all()
    
    alerts = []
    for disp, status in rows:
        alerts.append({
            "dispenser_id": disp.dispenser_id,
            "or_number": disp.or_number,
            "level_percent": status.level_percent,
            "status": status.status,
            "message": f"Dispenser at {status.level_percent:.0f}% - {status.status}"
        })
    
    return {"alerts": alerts, "count": len(alerts)}
