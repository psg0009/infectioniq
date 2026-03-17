"""
Camera Health Monitoring API
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth_deps import get_current_active_user
from app.models.user import User

router = APIRouter()


class CameraStatus(BaseModel):
    camera_id: str
    or_number: str
    status: str  # ONLINE, OFFLINE, DEGRADED
    fps: Optional[float] = None
    resolution: Optional[str] = None
    last_frame_at: Optional[datetime] = None
    uptime_percent: Optional[float] = None
    error_message: Optional[str] = None


# In-memory camera registry (production would use Redis/DB)
_camera_registry: dict[str, CameraStatus] = {}


@router.get("/")
async def list_cameras(user: User = Depends(get_current_active_user)):
    """List all registered cameras and their status"""
    return {"cameras": list(_camera_registry.values()), "total": len(_camera_registry)}


@router.get("/{camera_id}")
async def get_camera(camera_id: str):
    """Get specific camera status"""
    cam = _camera_registry.get(camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    return cam


@router.get("/{camera_id}/config")
async def get_camera_config(camera_id: str, db: AsyncSession = Depends(get_db)):
    """Return zone config and settings for a CV module instance.
    The CV module fetches this at startup to get zone polygons and gesture thresholds."""
    from app.config import settings
    from app.models.models import GestureProfile

    # Derive OR number from camera_id (e.g. "cam-OR-1" -> "OR-1")
    or_number = camera_id.replace("cam-", "", 1) if camera_id.startswith("cam-") else None

    # Look for LATEST VERSION of gesture profile matching this OR, falling back to default
    gesture_config = None
    profile_id = None
    if or_number:
        result = await db.execute(
            select(GestureProfile)
            .where(GestureProfile.or_number == or_number)
            .order_by(GestureProfile.version.desc())
            .limit(1)
        )
        profile = result.scalar_one_or_none()
        if profile:
            gesture_config = _profile_to_config(profile)
            profile_id = str(profile.id)

    if gesture_config is None:
        result = await db.execute(
            select(GestureProfile)
            .where(GestureProfile.is_default == True)
            .order_by(GestureProfile.version.desc())
            .limit(1)
        )
        profile = result.scalar_one_or_none()
        if profile:
            gesture_config = _profile_to_config(profile)
            profile_id = str(profile.id)

    response = {
        "camera_id": camera_id,
        "zones": settings.ZONE_CONFIG,
        "zone_risk_levels": settings.ZONE_RISK_LEVELS,
        "heartbeat_interval": 30,
        "thresholds": {
            "person_confidence": settings.PERSON_CONFIDENCE_THRESHOLD,
            "hand_confidence": settings.HAND_CONFIDENCE_THRESHOLD,
            "sanitize_gesture": settings.SANITIZE_GESTURE_THRESHOLD,
            "sanitize_min_duration_sec": settings.SANITIZE_MIN_DURATION_SEC,
        },
    }
    if gesture_config:
        response["gesture_config"] = gesture_config
        response["gesture_profile_id"] = profile_id
    return response


def _profile_to_config(profile) -> dict:
    """Convert a GestureProfile ORM row to a dict for the CV module."""
    return {
        "palm_distance_threshold": profile.palm_distance_threshold,
        "palm_variance_threshold": profile.palm_variance_threshold,
        "motion_threshold": profile.motion_threshold,
        "oscillation_threshold": profile.oscillation_threshold,
        "score_threshold": profile.score_threshold,
        "min_duration_sec": profile.min_duration_sec,
        "weight_palm_close": profile.weight_palm_close,
        "weight_palm_variance": profile.weight_palm_variance,
        "weight_motion": profile.weight_motion,
        "weight_oscillation": profile.weight_oscillation,
    }


@router.post("/heartbeat")
async def camera_heartbeat(
    status: CameraStatus,
):
    """Receive heartbeat from camera/CV module.
    No auth required — CV modules run as internal services without user credentials."""
    status.last_frame_at = datetime.utcnow()
    _camera_registry[status.camera_id] = status
    return {"status": "ok"}


@router.get("/health/summary")
async def camera_health_summary():
    """Get aggregate camera health summary"""
    total = len(_camera_registry)
    online = sum(1 for c in _camera_registry.values() if c.status == "ONLINE")
    degraded = sum(1 for c in _camera_registry.values() if c.status == "DEGRADED")
    offline = sum(1 for c in _camera_registry.values() if c.status == "OFFLINE")

    # Check for stale cameras
    from app.config import settings
    stale_threshold = datetime.utcnow() - timedelta(seconds=settings.CAMERA_STALE_THRESHOLD_SECONDS)
    for cam in _camera_registry.values():
        if cam.last_frame_at and cam.last_frame_at < stale_threshold:
            cam.status = "OFFLINE"

    return {
        "total": total,
        "online": online,
        "degraded": degraded,
        "offline": offline,
        "health_percent": (online / total * 100) if total > 0 else 0,
    }
