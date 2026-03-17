"""
Gesture Calibration API
Endpoints for managing calibration sessions, uploading samples,
running threshold sweeps, and applying results to gesture profiles.
"""

import itertools
import re
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rate_limit import rate_limit_dependency
from app.models.models import (
    GestureCalibrationSession,
    GestureCalibrationSample,
    GestureProfile,
)

router = APIRouter()

_VALID_LABELS = {"SANITIZING", "NOT_SANITIZING"}
_OR_NUMBER_RE = re.compile(r"^OR-\d{1,3}$")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class CalibrationSessionCreate(BaseModel):
    name: str
    or_number: Optional[str] = None
    observer_name: Optional[str] = None
    glove_type: Optional[str] = None
    dispenser_type: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("name", mode="before")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        v = str(v).strip()
        if not v or len(v) > 255:
            raise ValueError("name must be 1-255 characters")
        return v

    @field_validator("or_number", mode="before")
    @classmethod
    def validate_or(cls, v):
        if v is None:
            return v
        v = str(v).strip()
        if not _OR_NUMBER_RE.match(v):
            raise ValueError("or_number must match OR-<1-3 digits> (e.g. OR-1, OR-12)")
        return v


class SampleUpload(BaseModel):
    label: str  # SANITIZING or NOT_SANITIZING
    palm_distance: float
    palm_distance_var: float = 0.0
    avg_motion: float
    oscillation_count: int
    score: float

    @field_validator("label")
    @classmethod
    def validate_label(cls, v: str) -> str:
        if v not in _VALID_LABELS:
            raise ValueError(f"label must be one of {_VALID_LABELS}")
        return v

    @field_validator("palm_distance", "score")
    @classmethod
    def validate_unit_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("value must be between 0.0 and 1.0")
        return v

    @field_validator("palm_distance_var", "avg_motion")
    @classmethod
    def validate_non_negative_float(cls, v: float) -> float:
        if v < 0:
            raise ValueError("value must be >= 0")
        return v

    @field_validator("oscillation_count")
    @classmethod
    def validate_non_negative_int(cls, v: int) -> int:
        if v < 0:
            raise ValueError("oscillation_count must be >= 0")
        return v


class SampleBatchUpload(BaseModel):
    samples: List[SampleUpload]

    @field_validator("samples")
    @classmethod
    def validate_batch_size(cls, v: List[SampleUpload]) -> List[SampleUpload]:
        if len(v) < 1 or len(v) > 1000:
            raise ValueError("samples must contain 1-1000 items")
        return v


class SweepRequest(BaseModel):
    palm_dist_range: Optional[List[float]] = None
    motion_range: Optional[List[float]] = None
    oscillation_range: Optional[List[int]] = None
    score_range: Optional[List[float]] = None

    @field_validator("palm_dist_range", "motion_range", "score_range")
    @classmethod
    def validate_float_ranges(cls, v):
        if v is None:
            return v
        if len(v) > 10:
            raise ValueError("range arrays must have at most 10 elements")
        for x in v:
            if not 0.0 <= x <= 1.0:
                raise ValueError("range values must be between 0.0 and 1.0")
        return v

    @field_validator("oscillation_range")
    @classmethod
    def validate_int_range(cls, v):
        if v is None:
            return v
        if len(v) > 10:
            raise ValueError("oscillation_range must have at most 10 elements")
        for x in v:
            if not 0 <= x <= 100:
                raise ValueError("oscillation values must be between 0 and 100")
        return v


class ApplyRequest(BaseModel):
    profile_name: str
    or_number: Optional[str] = None
    palm_distance_threshold: float
    motion_threshold: float
    oscillation_threshold: int
    score_threshold: float

    @field_validator("profile_name", mode="before")
    @classmethod
    def sanitize_profile_name(cls, v: str) -> str:
        v = str(v).strip()
        if not v or len(v) > 100:
            raise ValueError("profile_name must be 1-100 characters")
        return v

    @field_validator("or_number", mode="before")
    @classmethod
    def validate_or(cls, v):
        if v is None:
            return v
        v = str(v).strip()
        if not _OR_NUMBER_RE.match(v):
            raise ValueError("or_number must match OR-<1-3 digits>")
        return v

    @field_validator("palm_distance_threshold", "motion_threshold", "score_threshold")
    @classmethod
    def validate_threshold_float(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("threshold must be between 0.0 and 1.0")
        return v

    @field_validator("oscillation_threshold")
    @classmethod
    def validate_threshold_int(cls, v: int) -> int:
        if not 0 <= v <= 100:
            raise ValueError("oscillation_threshold must be between 0 and 100")
        return v


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/sessions")
async def list_sessions(db: AsyncSession = Depends(get_db)):
    """List all calibration sessions with summary stats."""
    result = await db.execute(
        select(GestureCalibrationSession).order_by(
            GestureCalibrationSession.created_at.desc()
        )
    )
    sessions = result.scalars().all()
    return {
        "sessions": [
            {
                "id": str(s.id),
                "name": s.name,
                "or_number": s.or_number,
                "observer_name": s.observer_name,
                "glove_type": s.glove_type,
                "total_samples": s.total_samples,
                "sanitizing_count": s.sanitizing_count,
                "not_sanitizing_count": s.not_sanitizing_count,
                "best_accuracy": s.best_accuracy,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in sessions
        ],
        "total": len(sessions),
    }


@router.post("/sessions")
async def create_session(
    body: CalibrationSessionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new calibration session."""
    session = GestureCalibrationSession(
        id=uuid.uuid4(),
        name=body.name,
        or_number=body.or_number,
        observer_name=body.observer_name,
        glove_type=body.glove_type,
        dispenser_type=body.dispenser_type,
        notes=body.notes,
    )
    db.add(session)
    await db.commit()
    return {"id": str(session.id), "name": session.name}


@router.post("/sessions/{session_id}/samples")
async def upload_samples(
    session_id: str,
    body: SampleBatchUpload,
    db: AsyncSession = Depends(get_db),
):
    """Upload a batch of labeled samples to a calibration session."""
    result = await db.execute(
        select(GestureCalibrationSession).where(
            GestureCalibrationSession.id == session_id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    sanitizing = 0
    not_sanitizing = 0

    for s in body.samples:
        sample = GestureCalibrationSample(
            id=uuid.uuid4(),
            session_id=session_id,
            label=s.label,
            palm_distance=s.palm_distance,
            palm_distance_var=s.palm_distance_var,
            avg_motion=s.avg_motion,
            oscillation_count=s.oscillation_count,
            score=s.score,
        )
        db.add(sample)
        if s.label == "SANITIZING":
            sanitizing += 1
        else:
            not_sanitizing += 1

    session.total_samples = (session.total_samples or 0) + len(body.samples)
    session.sanitizing_count = (session.sanitizing_count or 0) + sanitizing
    session.not_sanitizing_count = (session.not_sanitizing_count or 0) + not_sanitizing

    await db.commit()
    return {
        "uploaded": len(body.samples),
        "total_samples": session.total_samples,
    }


@router.post("/sessions/{session_id}/sweep", dependencies=[Depends(rate_limit_dependency(5))])
async def run_sweep(
    session_id: str,
    body: SweepRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run a threshold sweep against all samples in this session."""
    result = await db.execute(
        select(GestureCalibrationSession).where(
            GestureCalibrationSession.id == session_id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    sample_result = await db.execute(
        select(GestureCalibrationSample).where(
            GestureCalibrationSample.session_id == session_id
        )
    )
    samples = sample_result.scalars().all()

    if not samples:
        raise HTTPException(status_code=400, detail="No samples in session")

    # Run threshold sweep
    palm_dist_range = body.palm_dist_range or [0.10, 0.12, 0.15, 0.18, 0.20]
    motion_range = body.motion_range or [0.01, 0.015, 0.02, 0.025, 0.03]
    oscillation_range = body.oscillation_range or [2, 3, 4, 5, 6]
    score_range = body.score_range or [0.5, 0.6, 0.7, 0.8, 0.9]

    results = []

    for palm_t, motion_t, osc_t, score_t in itertools.product(
        palm_dist_range, motion_range, oscillation_range, score_range
    ):
        tp = tn = fp = fn = 0

        for sample in samples:
            s = 0.0
            if sample.palm_distance < palm_t:
                s += 0.3
            if sample.palm_distance_var > 0.001:
                s += 0.2
            if sample.avg_motion > motion_t:
                s += 0.2
            if sample.oscillation_count >= osc_t:
                s += 0.3

            predicted = s >= score_t
            actual = sample.label == "SANITIZING"

            if predicted and actual:
                tp += 1
            elif not predicted and not actual:
                tn += 1
            elif predicted and not actual:
                fp += 1
            else:
                fn += 1

        total = tp + tn + fp + fn
        accuracy = (tp + tn) / total if total > 0 else 0
        sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0

        results.append({
            "palm_distance_threshold": palm_t,
            "motion_threshold": motion_t,
            "oscillation_threshold": osc_t,
            "score_threshold": score_t,
            "accuracy": round(accuracy, 4),
            "sensitivity": round(sensitivity, 4),
            "specificity": round(specificity, 4),
            "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        })

    results.sort(key=lambda r: r["accuracy"], reverse=True)

    # Update session best_accuracy
    if results:
        session.best_accuracy = results[0]["accuracy"]
        await db.commit()

    return {
        "total_combinations": len(results),
        "total_samples": len(samples),
        "best": results[0] if results else None,
        "top_10": results[:10],
    }


@router.post("/sessions/{session_id}/apply")
async def apply_thresholds(
    session_id: str,
    body: ApplyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Apply sweep-selected thresholds as a NEW versioned GestureProfile."""
    result = await db.execute(
        select(GestureCalibrationSession).where(
            GestureCalibrationSession.id == session_id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get latest version for this profile name
    latest_result = await db.execute(
        select(func.max(GestureProfile.version)).where(
            GestureProfile.name == body.profile_name
        )
    )
    latest_version = latest_result.scalar() or 0

    # Always create NEW row (immutable versioning)
    profile = GestureProfile(
        id=uuid.uuid4(),
        name=body.profile_name,
        version=latest_version + 1,
        palm_distance_threshold=body.palm_distance_threshold,
        motion_threshold=body.motion_threshold,
        oscillation_threshold=body.oscillation_threshold,
        score_threshold=body.score_threshold,
        or_number=body.or_number,
        calibration_session_id=session_id,
    )
    db.add(profile)

    await db.commit()
    return {
        "profile_id": str(profile.id),
        "profile_name": profile.name,
        "version": profile.version,
        "previous_version": latest_version if latest_version > 0 else None,
        "applied_thresholds": {
            "palm_distance_threshold": body.palm_distance_threshold,
            "motion_threshold": body.motion_threshold,
            "oscillation_threshold": body.oscillation_threshold,
            "score_threshold": body.score_threshold,
        },
    }


@router.get("/profiles/{profile_name}/versions")
async def list_profile_versions(
    profile_name: str,
    db: AsyncSession = Depends(get_db),
):
    """List all versions of a GestureProfile."""
    result = await db.execute(
        select(GestureProfile)
        .where(GestureProfile.name == profile_name)
        .order_by(GestureProfile.version.desc())
    )
    profiles = result.scalars().all()

    return {
        "profile_name": profile_name,
        "versions": [
            {
                "id": str(p.id),
                "version": p.version,
                "or_number": p.or_number,
                "calibration_session_id": str(p.calibration_session_id) if p.calibration_session_id else None,
                "thresholds": {
                    "palm_distance_threshold": p.palm_distance_threshold,
                    "motion_threshold": p.motion_threshold,
                    "oscillation_threshold": p.oscillation_threshold,
                    "score_threshold": p.score_threshold,
                },
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in profiles
        ],
        "total_versions": len(profiles),
    }
