"""
PostgreSQL Compatibility Tests

These tests verify that UUID36, enums, JSON columns, FK constraints,
and new gesture/validation tables work correctly on real PostgreSQL.

Run with:
  TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/testdb pytest -k postgres
"""

import uuid
from datetime import datetime

import pytest
from sqlalchemy import select

from tests.conftest_postgres import requires_postgres

from app.models.models import (
    SurgicalCase,
    RiskScore,
    TouchEvent,
    Alert,
    GestureProfile,
    GestureCalibrationSession,
    GestureCalibrationSample,
)


@requires_postgres
@pytest.mark.asyncio
async def test_uuid36_roundtrip(pg_session):
    """UUID36 columns store and retrieve correctly on PostgreSQL."""
    case_id = str(uuid.uuid4())
    case = SurgicalCase(
        id=case_id,
        or_number="OR-1",
        status="IN_PROGRESS",
    )
    pg_session.add(case)
    await pg_session.commit()

    result = await pg_session.execute(select(SurgicalCase).where(SurgicalCase.id == case_id))
    loaded = result.scalar_one()
    assert str(loaded.id) == case_id


@requires_postgres
@pytest.mark.asyncio
async def test_enum_storage(pg_session):
    """String-based enums (status, event_type, zone) persist correctly."""
    case_id = str(uuid.uuid4())
    case = SurgicalCase(id=case_id, or_number="OR-2", status="IN_PROGRESS")
    pg_session.add(case)
    await pg_session.flush()

    event = TouchEvent(
        id=str(uuid.uuid4()),
        case_id=case_id,
        person_id="P1",
        event_type="ENTRY",
        zone="STERILE",
    )
    pg_session.add(event)
    await pg_session.commit()

    result = await pg_session.execute(select(TouchEvent).where(TouchEvent.case_id == case_id))
    loaded = result.scalar_one()
    assert loaded.event_type == "ENTRY"
    assert loaded.zone == "STERILE"


@requires_postgres
@pytest.mark.asyncio
async def test_json_columns(pg_session):
    """JSON columns (factors on RiskScore) store and load correctly."""
    case_id = str(uuid.uuid4())
    case = SurgicalCase(id=case_id, or_number="OR-3", status="IN_PROGRESS")
    pg_session.add(case)
    await pg_session.flush()

    rs = RiskScore(
        case_id=case_id,
        score=75,
        risk_level="HIGH",
        factors={"proximity": 0.9, "duration": 5},
        recommendations=["Increase hand hygiene frequency"],
    )
    pg_session.add(rs)
    await pg_session.commit()

    result = await pg_session.execute(select(RiskScore).where(RiskScore.case_id == case_id))
    loaded = result.scalar_one()
    assert loaded.factors["proximity"] == 0.9
    assert loaded.recommendations[0] == "Increase hand hygiene frequency"


@requires_postgres
@pytest.mark.asyncio
async def test_fk_cascade_delete(pg_session):
    """FK cascade: deleting a calibration session cascades to its samples."""
    session_id = str(uuid.uuid4())
    session = GestureCalibrationSession(
        id=session_id,
        name="Cascade Test",
    )
    pg_session.add(session)
    await pg_session.flush()

    for i in range(3):
        sample = GestureCalibrationSample(
            id=str(uuid.uuid4()),
            session_id=session_id,
            label="SANITIZING",
            palm_distance=0.1,
            avg_motion=0.02,
            oscillation_count=4,
            score=0.8,
        )
        pg_session.add(sample)
    await pg_session.commit()

    # Verify samples exist
    result = await pg_session.execute(
        select(GestureCalibrationSample).where(GestureCalibrationSample.session_id == session_id)
    )
    assert len(result.scalars().all()) == 3

    # Delete session — samples should cascade
    await pg_session.delete(session)
    await pg_session.commit()

    result = await pg_session.execute(
        select(GestureCalibrationSample).where(GestureCalibrationSample.session_id == session_id)
    )
    assert len(result.scalars().all()) == 0


@requires_postgres
@pytest.mark.asyncio
async def test_gesture_calibration_end_to_end(pg_session):
    """Full gesture calibration flow: profile, session, samples."""
    # Create gesture profile
    profile = GestureProfile(
        id=str(uuid.uuid4()),
        name="OR-1 Profile",
        palm_distance_threshold=0.15,
        motion_threshold=0.02,
        oscillation_threshold=4,
        score_threshold=0.7,
        is_default=True,
        or_number="OR-1",
    )
    pg_session.add(profile)

    # Create calibration session
    cal_session = GestureCalibrationSession(
        id=str(uuid.uuid4()),
        name="Test Session",
        or_number="OR-1",
        observer_name="Dr. Test",
        glove_type="Latex",
        total_samples=2,
        sanitizing_count=1,
        not_sanitizing_count=1,
        best_accuracy=0.95,
    )
    pg_session.add(cal_session)
    await pg_session.flush()

    # Add samples
    for label in ["SANITIZING", "NOT_SANITIZING"]:
        pg_session.add(GestureCalibrationSample(
            id=str(uuid.uuid4()),
            session_id=str(cal_session.id),
            label=label,
            palm_distance=0.12,
            palm_distance_var=0.001,
            avg_motion=0.03,
            oscillation_count=5,
            score=0.85,
        ))
    await pg_session.commit()

    # Query back
    result = await pg_session.execute(select(GestureProfile).where(GestureProfile.or_number == "OR-1"))
    loaded_profile = result.scalar_one()
    assert loaded_profile.is_default is True
    assert loaded_profile.palm_distance_threshold == 0.15


@requires_postgres
@pytest.mark.asyncio
async def test_validation_observations_with_gesture_score(pg_session):
    """ValidationObservation stores system_gesture_score on PostgreSQL."""
    from app.services.clinical_validation import ValidationSession, ValidationObservation

    case_id = str(uuid.uuid4())
    case = SurgicalCase(id=case_id, or_number="OR-5", status="IN_PROGRESS")
    pg_session.add(case)
    await pg_session.flush()

    vs = ValidationSession(
        id=str(uuid.uuid4()),
        case_id=case_id,
        observer_name="Observer A",
    )
    pg_session.add(vs)
    await pg_session.flush()

    vo = ValidationObservation(
        id=str(uuid.uuid4()),
        session_id=str(vs.id),
        timestamp=datetime.utcnow(),
        event_type="SANITIZE",
        observed_compliant=True,
        system_compliant=True,
        system_gesture_score=0.87,
    )
    pg_session.add(vo)
    await pg_session.commit()

    result = await pg_session.execute(
        select(ValidationObservation).where(ValidationObservation.session_id == str(vs.id))
    )
    loaded = result.scalar_one()
    assert loaded.system_gesture_score == pytest.approx(0.87)
    assert loaded.event_type == "SANITIZE"
