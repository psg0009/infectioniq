"""Tests for clinical validation matching algorithm"""

import pytest
import pytest_asyncio
import uuid
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.clinical_validation import (
    ValidationSession,
    ValidationObservation,
    calculate_validation_metrics,
    match_observations_to_system,
    MATCH_WINDOW_SECONDS,
)
from app.models.models import SurgicalCase, EntryExitEvent, TouchEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_case(db: AsyncSession) -> str:
    """Create a surgical case and return its id."""
    case_id = str(uuid.uuid4())
    case = SurgicalCase(
        id=case_id,
        or_number="OR-1",
        procedure_type="Appendectomy",
        status="IN_PROGRESS",
        start_time=datetime.utcnow(),
    )
    db.add(case)
    await db.flush()
    return case_id


async def _create_validation_session(db: AsyncSession, case_id: str) -> str:
    """Create a validation session and return its id."""
    session_id = str(uuid.uuid4())
    session = ValidationSession(
        id=session_id,
        case_id=case_id,
        observer_name="Dr. Observer",
    )
    db.add(session)
    await db.flush()
    return session_id


async def _create_observation(
    db: AsyncSession,
    session_id: str,
    timestamp: datetime,
    event_type: str = "ENTRY",
    observed_compliant: bool = True,
    staff_id: str = None,
) -> str:
    obs_id = str(uuid.uuid4())
    obs = ValidationObservation(
        id=obs_id,
        session_id=session_id,
        timestamp=timestamp,
        event_type=event_type,
        observed_compliant=observed_compliant,
        staff_id=staff_id,
    )
    db.add(obs)
    await db.flush()
    return obs_id


async def _create_system_event(
    db: AsyncSession,
    case_id: str,
    timestamp: datetime,
    event_type: str = "ENTRY",
    compliant: bool = True,
    staff_id: str = None,
) -> str:
    evt_id = str(uuid.uuid4())
    evt = EntryExitEvent(
        id=evt_id,
        case_id=case_id,
        person_track_id=1,
        event_type=event_type,
        timestamp=timestamp,
        compliant=compliant,
        staff_id=staff_id,
    )
    db.add(evt)
    await db.flush()
    return evt_id


# ---------------------------------------------------------------------------
# match_observations_to_system
# ---------------------------------------------------------------------------

class TestMatchObservationsToSystem:
    @pytest.mark.asyncio
    async def test_session_not_found(self, db_session: AsyncSession):
        result = await match_observations_to_system("nonexistent-id", db_session)
        assert "error" in result
        assert result["error"] == "Session not found"

    @pytest.mark.asyncio
    async def test_no_unmatched_observations(self, db_session: AsyncSession):
        case_id = await _create_case(db_session)
        session_id = await _create_validation_session(db_session, case_id)
        result = await match_observations_to_system(session_id, db_session)
        assert result["matched"] == 0
        assert result["unmatched"] == 0

    @pytest.mark.asyncio
    async def test_exact_match(self, db_session: AsyncSession):
        """Observer and system event at the same time, same type -> match"""
        now = datetime.utcnow()
        case_id = await _create_case(db_session)
        session_id = await _create_validation_session(db_session, case_id)

        await _create_observation(db_session, session_id, now, "ENTRY", True)
        await _create_system_event(db_session, case_id, now, "ENTRY", True)

        result = await match_observations_to_system(session_id, db_session)
        assert result["matched"] == 1
        assert result["unmatched"] == 0

    @pytest.mark.asyncio
    async def test_match_within_window(self, db_session: AsyncSession):
        """Events within MATCH_WINDOW_SECONDS should match"""
        now = datetime.utcnow()
        case_id = await _create_case(db_session)
        session_id = await _create_validation_session(db_session, case_id)

        await _create_observation(db_session, session_id, now, "ENTRY", True)
        await _create_system_event(
            db_session, case_id, now + timedelta(seconds=20), "ENTRY", True
        )

        result = await match_observations_to_system(session_id, db_session)
        assert result["matched"] == 1

    @pytest.mark.asyncio
    async def test_no_match_outside_window(self, db_session: AsyncSession):
        """Events outside MATCH_WINDOW_SECONDS should NOT match"""
        now = datetime.utcnow()
        case_id = await _create_case(db_session)
        session_id = await _create_validation_session(db_session, case_id)

        await _create_observation(db_session, session_id, now, "ENTRY", True)
        await _create_system_event(
            db_session, case_id, now + timedelta(seconds=60), "ENTRY", True
        )

        result = await match_observations_to_system(session_id, db_session)
        assert result["matched"] == 0
        assert result["unmatched"] == 1

    @pytest.mark.asyncio
    async def test_type_mismatch(self, db_session: AsyncSession):
        """Different event types should not match"""
        now = datetime.utcnow()
        case_id = await _create_case(db_session)
        session_id = await _create_validation_session(db_session, case_id)

        await _create_observation(db_session, session_id, now, "ENTRY", True)
        await _create_system_event(db_session, case_id, now, "EXIT", True)

        result = await match_observations_to_system(session_id, db_session)
        assert result["matched"] == 0
        assert result["unmatched"] == 1

    @pytest.mark.asyncio
    async def test_hand_hygiene_maps_to_entry(self, db_session: AsyncSession):
        """HAND_HYGIENE observer event should match ENTRY system event"""
        now = datetime.utcnow()
        case_id = await _create_case(db_session)
        session_id = await _create_validation_session(db_session, case_id)

        await _create_observation(db_session, session_id, now, "HAND_HYGIENE", True)
        await _create_system_event(db_session, case_id, now, "ENTRY", True)

        result = await match_observations_to_system(session_id, db_session)
        assert result["matched"] == 1

    @pytest.mark.asyncio
    async def test_staff_id_mismatch(self, db_session: AsyncSession):
        """When both have staff_id, they must match"""
        now = datetime.utcnow()
        case_id = await _create_case(db_session)
        session_id = await _create_validation_session(db_session, case_id)

        staff_a = str(uuid.uuid4())
        staff_b = str(uuid.uuid4())

        await _create_observation(
            db_session, session_id, now, "ENTRY", True, staff_id=staff_a
        )
        await _create_system_event(
            db_session, case_id, now, "ENTRY", True, staff_id=staff_b
        )

        result = await match_observations_to_system(session_id, db_session)
        assert result["matched"] == 0
        assert result["unmatched"] == 1

    @pytest.mark.asyncio
    async def test_staff_id_matches_correctly(self, db_session: AsyncSession):
        """Same staff_id on both sides -> match"""
        now = datetime.utcnow()
        case_id = await _create_case(db_session)
        session_id = await _create_validation_session(db_session, case_id)

        staff_id = str(uuid.uuid4())

        await _create_observation(
            db_session, session_id, now, "ENTRY", True, staff_id=staff_id
        )
        await _create_system_event(
            db_session, case_id, now, "ENTRY", False, staff_id=staff_id
        )

        result = await match_observations_to_system(session_id, db_session)
        assert result["matched"] == 1

    @pytest.mark.asyncio
    async def test_closest_match_wins(self, db_session: AsyncSession):
        """When multiple system events could match, pick the closest in time"""
        now = datetime.utcnow()
        case_id = await _create_case(db_session)
        session_id = await _create_validation_session(db_session, case_id)

        await _create_observation(db_session, session_id, now, "ENTRY", True)
        await _create_system_event(
            db_session, case_id, now + timedelta(seconds=25), "ENTRY", False
        )
        await _create_system_event(
            db_session, case_id, now + timedelta(seconds=5), "ENTRY", True
        )

        result = await match_observations_to_system(session_id, db_session)
        assert result["matched"] == 1

    @pytest.mark.asyncio
    async def test_system_event_not_reused(self, db_session: AsyncSession):
        """Each system event should only be matched once"""
        now = datetime.utcnow()
        case_id = await _create_case(db_session)
        session_id = await _create_validation_session(db_session, case_id)

        await _create_observation(db_session, session_id, now, "ENTRY", True)
        await _create_observation(
            db_session, session_id, now + timedelta(seconds=5), "ENTRY", True
        )
        # Only one system event
        await _create_system_event(db_session, case_id, now, "ENTRY", True)

        result = await match_observations_to_system(session_id, db_session)
        assert result["matched"] == 1
        assert result["unmatched"] == 1

    @pytest.mark.asyncio
    async def test_already_matched_observations_skipped(self, db_session: AsyncSession):
        """Observations with system_compliant already set should be skipped"""
        now = datetime.utcnow()
        case_id = await _create_case(db_session)
        session_id = await _create_validation_session(db_session, case_id)

        # Create a pre-matched observation
        obs = ValidationObservation(
            id=str(uuid.uuid4()),
            session_id=session_id,
            timestamp=now,
            event_type="ENTRY",
            observed_compliant=True,
            system_compliant=True,  # Already matched
        )
        db_session.add(obs)
        await db_session.flush()

        result = await match_observations_to_system(session_id, db_session)
        assert result["matched"] == 0
        assert result["unmatched"] == 0


# ---------------------------------------------------------------------------
# calculate_validation_metrics
# ---------------------------------------------------------------------------

class TestCalculateValidationMetrics:
    @pytest.mark.asyncio
    async def test_no_matched_observations(self, db_session: AsyncSession):
        case_id = await _create_case(db_session)
        session_id = await _create_validation_session(db_session, case_id)
        result = await calculate_validation_metrics(session_id, db_session)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_perfect_accuracy(self, db_session: AsyncSession):
        """All observations match system -> 100% accuracy"""
        now = datetime.utcnow()
        case_id = await _create_case(db_session)
        session_id = await _create_validation_session(db_session, case_id)

        # 3 true positives
        for _ in range(3):
            db_session.add(ValidationObservation(
                id=str(uuid.uuid4()),
                session_id=session_id,
                timestamp=now,
                event_type="ENTRY",
                observed_compliant=True,
                system_compliant=True,
            ))
        # 2 true negatives
        for _ in range(2):
            db_session.add(ValidationObservation(
                id=str(uuid.uuid4()),
                session_id=session_id,
                timestamp=now,
                event_type="ENTRY",
                observed_compliant=False,
                system_compliant=False,
            ))
        await db_session.flush()

        result = await calculate_validation_metrics(session_id, db_session)
        assert result["accuracy"] == 1.0
        assert result["sensitivity"] == 1.0
        assert result["specificity"] == 1.0
        assert result["total_observations"] == 5

    @pytest.mark.asyncio
    async def test_mixed_results(self, db_session: AsyncSession):
        """Test with a mix of TP, TN, FP, FN"""
        now = datetime.utcnow()
        case_id = await _create_case(db_session)
        session_id = await _create_validation_session(db_session, case_id)

        observations = [
            (True, True),   # TP
            (True, False),  # FN
            (False, False), # TN
            (False, True),  # FP
        ]
        for observed, system in observations:
            db_session.add(ValidationObservation(
                id=str(uuid.uuid4()),
                session_id=session_id,
                timestamp=now,
                event_type="ENTRY",
                observed_compliant=observed,
                system_compliant=system,
            ))
        await db_session.flush()

        result = await calculate_validation_metrics(session_id, db_session)
        assert result["true_positives"] == 1
        assert result["true_negatives"] == 1
        assert result["false_positives"] == 1
        assert result["false_negatives"] == 1
        assert result["accuracy"] == 0.5
        assert result["sensitivity"] == 0.5
        assert result["specificity"] == 0.5


# ---------------------------------------------------------------------------
# Helpers for SANITIZE matching
# ---------------------------------------------------------------------------

async def _create_touch_event(
    db: AsyncSession,
    case_id: str,
    timestamp: datetime,
    zone: str = "SANITIZER",
    confidence: float = 0.85,
    staff_id: str = None,
) -> str:
    evt_id = str(uuid.uuid4())
    evt = TouchEvent(
        id=evt_id,
        case_id=case_id,
        person_track_id=1,
        timestamp=timestamp,
        zone=zone,
        hand="RIGHT",
        confidence=confidence,
        staff_id=staff_id,
    )
    db.add(evt)
    await db.flush()
    return evt_id


# ---------------------------------------------------------------------------
# SANITIZE observation matching
# ---------------------------------------------------------------------------

class TestSanitizeMatching:
    @pytest.mark.asyncio
    async def test_sanitize_matches_touch_in_sanitizer_zone(self, db_session: AsyncSession):
        """SANITIZE observation matches a TouchEvent in SANITIZER zone"""
        now = datetime.utcnow()
        case_id = await _create_case(db_session)
        session_id = await _create_validation_session(db_session, case_id)

        await _create_observation(db_session, session_id, now, "SANITIZE", True)
        await _create_touch_event(db_session, case_id, now, "SANITIZER", 0.9)

        result = await match_observations_to_system(session_id, db_session)
        assert result["matched"] == 1
        assert result["unmatched"] == 0

    @pytest.mark.asyncio
    async def test_sanitize_no_match_wrong_zone(self, db_session: AsyncSession):
        """SANITIZE observation does NOT match a TouchEvent in non-SANITIZER zone"""
        now = datetime.utcnow()
        case_id = await _create_case(db_session)
        session_id = await _create_validation_session(db_session, case_id)

        await _create_observation(db_session, session_id, now, "SANITIZE", True)
        await _create_touch_event(db_session, case_id, now, "STERILE", 0.9)

        result = await match_observations_to_system(session_id, db_session)
        assert result["matched"] == 0
        assert result["unmatched"] == 1

    @pytest.mark.asyncio
    async def test_sanitize_match_within_window(self, db_session: AsyncSession):
        """SANITIZE observation matches touch event within time window"""
        now = datetime.utcnow()
        case_id = await _create_case(db_session)
        session_id = await _create_validation_session(db_session, case_id)

        await _create_observation(db_session, session_id, now, "SANITIZE", True)
        await _create_touch_event(
            db_session, case_id, now + timedelta(seconds=20), "SANITIZER", 0.85
        )

        result = await match_observations_to_system(session_id, db_session)
        assert result["matched"] == 1

    @pytest.mark.asyncio
    async def test_sanitize_no_match_outside_window(self, db_session: AsyncSession):
        """SANITIZE observation outside time window does NOT match"""
        now = datetime.utcnow()
        case_id = await _create_case(db_session)
        session_id = await _create_validation_session(db_session, case_id)

        await _create_observation(db_session, session_id, now, "SANITIZE", True)
        await _create_touch_event(
            db_session, case_id, now + timedelta(seconds=60), "SANITIZER", 0.85
        )

        result = await match_observations_to_system(session_id, db_session)
        assert result["matched"] == 0
        assert result["unmatched"] == 1

    @pytest.mark.asyncio
    async def test_mixed_entry_and_sanitize(self, db_session: AsyncSession):
        """Mix of ENTRY and SANITIZE observations both get matched"""
        now = datetime.utcnow()
        case_id = await _create_case(db_session)
        session_id = await _create_validation_session(db_session, case_id)

        # ENTRY observation + system event
        await _create_observation(db_session, session_id, now, "ENTRY", True)
        await _create_system_event(db_session, case_id, now, "ENTRY", True)

        # SANITIZE observation + touch event
        await _create_observation(
            db_session, session_id, now + timedelta(seconds=5), "SANITIZE", True
        )
        await _create_touch_event(
            db_session, case_id, now + timedelta(seconds=5), "SANITIZER", 0.9
        )

        result = await match_observations_to_system(session_id, db_session)
        assert result["matched"] == 2
        assert result["unmatched"] == 0
