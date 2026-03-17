"""Pricing API"""

from fastapi import APIRouter
from app.core.pricing_tiers import get_pricing

router = APIRouter()


@router.get("/")
async def list_pricing():
    """Get pricing tiers"""
    return {"tiers": get_pricing()}
