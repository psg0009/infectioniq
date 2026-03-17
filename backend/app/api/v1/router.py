"""
API Router - Main router combining all endpoints

Auth & Subscription enforcement:
- Public: auth, sso, pricing (no token needed)
- Protected: all others require a valid JWT
- Role-gated: reports, fhir, validation, calibration require ADMIN/MANAGER
- Tier-gated: fhir, calibration, validation require PROFESSIONAL+
"""

from fastapi import APIRouter, Depends
from app.core.auth_deps import get_current_active_user, require_role
from app.core.enums import UserRole
from app.core.subscription import require_feature
from app.api.v1 import (
    cases, compliance, alerts, staff, dispensers, analytics,
    auth, consent, fhir, sso, cameras, reports, roi,
    validation, pricing, calibration, video,
)

api_router = APIRouter()

# ── Public routes (no auth required) ──────────────────────────────────
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(sso.router, prefix="/sso", tags=["SSO"])
api_router.include_router(pricing.router, prefix="/pricing", tags=["Pricing"])

# ── Protected routes (require authenticated user, any tier) ───────────
_auth = [Depends(get_current_active_user)]

api_router.include_router(cases.router, prefix="/cases", tags=["Cases"], dependencies=_auth)
api_router.include_router(compliance.router, prefix="/compliance", tags=["Compliance"], dependencies=_auth)
api_router.include_router(alerts.router, prefix="/alerts", tags=["Alerts"], dependencies=_auth)
api_router.include_router(staff.router, prefix="/staff", tags=["Staff"], dependencies=_auth)
api_router.include_router(dispensers.router, prefix="/dispensers", tags=["Dispensers"], dependencies=_auth)
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"], dependencies=_auth)
api_router.include_router(video.router, prefix="/video", tags=["Video Upload"], dependencies=_auth)
api_router.include_router(roi.router, prefix="/roi", tags=["ROI"], dependencies=_auth)

# ── Tier-gated routes (require PROFESSIONAL or higher) ────────────────
api_router.include_router(
    consent.router, prefix="/consent", tags=["Consent"],
    dependencies=[Depends(require_feature("consent"))],
)
api_router.include_router(
    cameras.router, prefix="/cameras", tags=["Cameras"],
    dependencies=[Depends(require_feature("cameras"))],
)

# ── Role + tier-gated routes (ADMIN/MANAGER + PROFESSIONAL+) ─────────
_manager_plus = [Depends(require_role(UserRole.ADMIN, UserRole.MANAGER))]

api_router.include_router(
    reports.router, prefix="/reports", tags=["Reports"],
    dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.MANAGER)),
                  Depends(require_feature("reports_csv"))],
)
api_router.include_router(
    fhir.router, prefix="/fhir", tags=["FHIR"],
    dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.MANAGER)),
                  Depends(require_feature("fhir"))],
)
api_router.include_router(
    validation.router, prefix="/validation", tags=["Clinical Validation"],
    dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.MANAGER)),
                  Depends(require_feature("validation"))],
)
api_router.include_router(
    calibration.router, prefix="/calibration", tags=["Gesture Calibration"],
    dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.MANAGER)),
                  Depends(require_feature("calibration"))],
)
