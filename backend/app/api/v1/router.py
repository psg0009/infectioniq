"""
API Router - Main router combining all endpoints
"""

from fastapi import APIRouter
from app.api.v1 import cases, compliance, alerts, staff, dispensers, analytics

api_router = APIRouter()

api_router.include_router(cases.router, prefix="/cases", tags=["Cases"])
api_router.include_router(compliance.router, prefix="/compliance", tags=["Compliance"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["Alerts"])
api_router.include_router(staff.router, prefix="/staff", tags=["Staff"])
api_router.include_router(dispensers.router, prefix="/dispensers", tags=["Dispensers"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
