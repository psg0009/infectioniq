"""ROI Calculator API"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from app.services.roi_calculator import ROIInputs, calculate_roi

router = APIRouter()


class ROIRequest(BaseModel):
    annual_surgical_cases: int = 5000
    baseline_ssi_rate: float = 0.02
    avg_ssi_cost: float = 25000
    system_annual_cost: float = 50000
    expected_ssi_reduction: float = 0.30
    implementation_cost: float = 25000
    staff_training_hours: int = 40
    hourly_staff_rate: float = 50


@router.post("/calculate")
async def calculate(request: ROIRequest):
    """Calculate ROI for InfectionIQ implementation"""
    inputs = ROIInputs(**request.model_dump())
    result = calculate_roi(inputs)
    return {
        "inputs": request.model_dump(),
        "results": {
            "baseline_ssi_cases": result.baseline_ssi_cases,
            "baseline_ssi_cost": result.baseline_ssi_cost,
            "projected_ssi_cases": result.projected_ssi_cases,
            "projected_ssi_cost": result.projected_ssi_cost,
            "annual_savings": result.annual_savings,
            "net_annual_savings": result.net_annual_savings,
            "first_year_savings": result.first_year_savings,
            "roi_percent": result.roi_percent,
            "payback_months": result.payback_months,
            "five_year_net_savings": result.five_year_net_savings,
        },
    }
