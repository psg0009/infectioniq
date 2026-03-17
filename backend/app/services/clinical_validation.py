"""
Clinical Validation Framework
Tools for validating system accuracy against human observers
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select, func, Integer, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base
from sqlalchemy import Column, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.sql import func as sqlfunc
import uuid as _uuid

logger = logging.getLogger(__name__)


class ValidationSession(Base):
    __tablename__ = "validation_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("surgical_cases.id"), nullable=False)
    observer_name = Column(String(255), nullable=False)
    started_at = Column(DateTime, server_default=sqlfunc.now())
    ended_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)


class ValidationObservation(Base):
    __tablename__ = "validation_observations"

    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("validation_sessions.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    event_type = Column(String(50), nullable=False)  # ENTRY, EXIT, HAND_HYGIENE, SANITIZE, TOUCH
    observed_compliant = Column(Boolean, nullable=False)
    system_compliant = Column(Boolean, nullable=True)  # filled by matching algorithm
    system_gesture_score = Column(Float, nullable=True)  # gesture score from matched system event
    staff_id = Column(String(36), nullable=True)
    notes = Column(Text, nullable=True)


async def calculate_validation_metrics(
    session_id: str, db: AsyncSession
) -> Dict[str, float]:
    """Calculate sensitivity, specificity, accuracy for a validation session"""
    result = await db.execute(
        select(ValidationObservation).where(
            ValidationObservation.session_id == session_id,
            ValidationObservation.system_compliant.isnot(None),
        )
    )
    observations = result.scalars().all()

    if not observations:
        return {"error": "No matched observations found"}

    tp = sum(1 for o in observations if o.observed_compliant and o.system_compliant)
    tn = sum(1 for o in observations if not o.observed_compliant and not o.system_compliant)
    fp = sum(1 for o in observations if not o.observed_compliant and o.system_compliant)
    fn = sum(1 for o in observations if o.observed_compliant and not o.system_compliant)

    total = tp + tn + fp + fn
    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
    accuracy = (tp + tn) / total if total > 0 else 0
    ppv = tp / (tp + fp) if (tp + fp) > 0 else 0
    npv = tn / (tn + fn) if (tn + fn) > 0 else 0

    return {
        "total_observations": total,
        "true_positives": tp,
        "true_negatives": tn,
        "false_positives": fp,
        "false_negatives": fn,
        "sensitivity": round(sensitivity, 4),
        "specificity": round(specificity, 4),
        "accuracy": round(accuracy, 4),
        "ppv": round(ppv, 4),
        "npv": round(npv, 4),
    }


# Time window for matching: observer event must be within this many seconds
# of a system event to be considered a match
MATCH_WINDOW_SECONDS = 30


async def match_observations_to_system(
    session_id: str, db: AsyncSession
) -> Dict[str, any]:
    """Match human observer observations against system-detected events.

    For each unmatched observation in the session, find the closest system
    EntryExitEvent within MATCH_WINDOW_SECONDS that has the same event_type
    (and optionally staff_id). Populate the observation's system_compliant
    field with the system's compliance determination.

    Returns a summary of matched/unmatched counts.
    """
    from app.models.models import EntryExitEvent, TouchEvent

    # Get the session to find the case_id
    session_result = await db.execute(
        select(ValidationSession).where(ValidationSession.id == session_id)
    )
    session = session_result.scalar_one_or_none()
    if not session:
        return {"error": "Session not found"}

    # Get all unmatched observations for this session
    obs_result = await db.execute(
        select(ValidationObservation).where(
            ValidationObservation.session_id == session_id,
            ValidationObservation.system_compliant.is_(None),
        ).order_by(ValidationObservation.timestamp)
    )
    observations = obs_result.scalars().all()

    if not observations:
        return {"matched": 0, "unmatched": 0, "message": "No unmatched observations"}

    # Separate SANITIZE observations from ENTRY/EXIT observations
    sanitize_obs = [o for o in observations if o.event_type.upper() == "SANITIZE"]
    entry_exit_obs = [o for o in observations if o.event_type.upper() != "SANITIZE"]

    # Get all system events for this case within the session time range
    earliest = min(o.timestamp for o in observations) - timedelta(seconds=MATCH_WINDOW_SECONDS)
    latest = max(o.timestamp for o in observations) + timedelta(seconds=MATCH_WINDOW_SECONDS)

    # Match ENTRY/EXIT observations against EntryExitEvents
    sys_result = await db.execute(
        select(EntryExitEvent).where(
            EntryExitEvent.case_id == session.case_id,
            EntryExitEvent.timestamp >= earliest,
            EntryExitEvent.timestamp <= latest,
        ).order_by(EntryExitEvent.timestamp)
    )
    system_events = sys_result.scalars().all()

    used_system_ids = set()
    matched = 0
    unmatched = 0

    for obs in entry_exit_obs:
        best_match = None
        best_delta = float("inf")

        for sys_evt in system_events:
            if str(sys_evt.id) in used_system_ids:
                continue

            # Must match event type (map HAND_HYGIENE -> ENTRY for observer shorthand)
            obs_type = obs.event_type.upper()
            sys_type = sys_evt.event_type.upper()
            if obs_type == "HAND_HYGIENE":
                obs_type = "ENTRY"
            if obs_type != sys_type:
                continue

            # If observer recorded a staff_id, require it to match
            if obs.staff_id and sys_evt.staff_id:
                if str(obs.staff_id) != str(sys_evt.staff_id):
                    continue

            delta = abs((obs.timestamp - sys_evt.timestamp).total_seconds())
            if delta <= MATCH_WINDOW_SECONDS and delta < best_delta:
                best_delta = delta
                best_match = sys_evt

        if best_match:
            obs.system_compliant = best_match.compliant
            used_system_ids.add(str(best_match.id))
            matched += 1
        else:
            obs.system_compliant = False
            unmatched += 1

    # Match SANITIZE observations against TouchEvents in SANITIZER zone
    if sanitize_obs:
        touch_result = await db.execute(
            select(TouchEvent).where(
                TouchEvent.case_id == session.case_id,
                TouchEvent.zone == "SANITIZER",
                TouchEvent.timestamp >= earliest,
                TouchEvent.timestamp <= latest,
            ).order_by(TouchEvent.timestamp)
        )
        sanitize_events = touch_result.scalars().all()

        used_touch_ids = set()

        for obs in sanitize_obs:
            best_match = None
            best_delta = float("inf")

            for touch_evt in sanitize_events:
                if str(touch_evt.id) in used_touch_ids:
                    continue

                if obs.staff_id and touch_evt.staff_id:
                    if str(obs.staff_id) != str(touch_evt.staff_id):
                        continue

                delta = abs((obs.timestamp - touch_evt.timestamp).total_seconds())
                if delta <= MATCH_WINDOW_SECONDS and delta < best_delta:
                    best_delta = delta
                    best_match = touch_evt

            if best_match:
                # System detected sanitization in SANITIZER zone = compliant
                obs.system_compliant = True
                obs.system_gesture_score = best_match.confidence
                used_touch_ids.add(str(best_match.id))
                matched += 1
            else:
                obs.system_compliant = False
                unmatched += 1

    await db.commit()

    return {
        "matched": matched,
        "unmatched": unmatched,
        "total_observations": len(observations),
        "total_system_events": len(system_events) + (len(sanitize_events) if sanitize_obs else 0),
    }
