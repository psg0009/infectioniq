"""
Demo Seed Script
=================
Populates the database with realistic-looking data for demos and presentations.
Run: python -m scripts.demo_seed

Generates:
  - 8 staff members across roles
  - 12 surgical cases (mix of active, completed, scheduled)
  - ~200 entry/exit events with realistic compliance rates
  - ~50 touch events
  - ~30 alerts (mix of acknowledged/unresolved)
  - 4 dispensers with varying levels
"""

import asyncio
import random
import uuid
from datetime import datetime, timedelta

# ── Configuration ────────────────────────────────────────────────────────────

NUM_STAFF = 8
NUM_COMPLETED_CASES = 8
NUM_ACTIVE_CASES = 3
NUM_SCHEDULED_CASES = 1
ENTRIES_PER_CASE = (0, 0)
TOUCH_EVENTS_PER_CASE = (0, 0)
COMPLIANCE_RATE = 0.82  # 82% average — realistic for a hospital trying to improve
NUM_ALERTS_PER_CASE = (0, 0)  # No fake alerts; real events come from CV pipeline

OR_NUMBERS = ["OR-1", "OR-2", "OR-3", "OR-4"]

STAFF_DATA: list[tuple[str, str, str]] = [
    ("Dr. Sarah Chen", "SURGEON", "Orthopedics"),
    ("Dr. James Patel", "SURGEON", "Cardiac"),
    ("Maria Gonzalez, RN", "NURSE", "Perioperative"),
    ("David Kim, RN", "NURSE", "Perioperative"),
    ("Lisa Thompson, CST", "TECH", "Sterile Processing"),
    ("Robert Jackson", "ANESTHESIOLOGIST", "Anesthesiology"),
    ("Dr. Amy Liu", "RESIDENT", "General Surgery"),
    ("Carlos Rivera, RN", "NURSE", "Perioperative"),
]

PROCEDURES = [
    ("Total Knee Replacement", "CPT-27447", "CLEAN", 2.5, 6.5),
    ("Hip Arthroplasty", "CPT-27130", "CLEAN", 3.0, 7.0),
    ("Spinal Fusion L4-L5", "CPT-22612", "CLEAN", 4.0, 8.5),
    ("Laparoscopic Cholecystectomy", "CPT-47562", "CLEAN_CONTAMINATED", 1.5, 4.0),
    ("Appendectomy", "CPT-44970", "CONTAMINATED", 1.0, 5.0),
    ("Coronary Artery Bypass", "CPT-33533", "CLEAN", 5.0, 9.0),
    ("Rotator Cuff Repair", "CPT-29827", "CLEAN", 2.0, 5.5),
    ("Hernia Repair", "CPT-49505", "CLEAN_CONTAMINATED", 1.5, 3.5),
    ("Craniotomy", "CPT-61510", "CLEAN", 4.5, 9.5),
    ("Total Shoulder Replacement", "CPT-23472", "CLEAN", 3.0, 7.5),
    ("ACL Reconstruction", "CPT-29888", "CLEAN", 2.0, 6.0),
    ("Thyroidectomy", "CPT-60240", "CLEAN", 2.5, 5.0),
]

ZONES = ["CRITICAL", "STERILE", "NON_STERILE", "DOOR", "SANITIZER"]  # converted to Zone enum below
ALERT_TYPES = ["CONTAMINATION", "MISSED_HYGIENE", "HIGH_RISK", "CRITICAL_ZONE"]  # converted to AlertType below
ALERT_SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]  # converted to AlertSeverity below


async def seed_demo_data():
    """Main seeding function."""
    import os
    import sys

    # Add backend to path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    os.environ.setdefault("USE_FAKEREDIS", "true")

    from app.core.database import async_session_maker, init_db
    from app.models.models import (
        Staff, SurgicalCase, RiskScore, EntryExitEvent,
        TouchEvent, Alert, Dispenser, DispenserStatus,
    )
    from app.core.enums import (
        StaffRole, WoundClass, CaseStatus, RiskLevel, Zone,
        AlertType, AlertSeverity, PersonState,
    )
    # Import all models so SQLAlchemy metadata is complete
    from app.models.user import User  # noqa: F401
    from app.models.audit_log import AuditLog  # noqa: F401
    from app.models.consent import PatientConsent  # noqa: F401
    from app.core.tenant import Organization  # noqa: F401

    await init_db()

    async with async_session_maker() as db:
        now = datetime.utcnow()

        # ── Demo User (login: demo@infectioniq.io / Demo@2024) ─────
        from app.core.security import hash_password
        from app.core.enums import UserRole
        demo_user = User(
            email="demo@infectioniq.io",
            password_hash=hash_password("Demo@2024"),
            full_name="Demo Admin",
            role=UserRole.ADMIN,
            is_active=True,
            is_superuser=True,
        )
        db.add(demo_user)
        await db.flush()
        print("  Created demo user: demo@infectioniq.io / Demo@2024")

        # ── Staff ────────────────────────────────────────────────────────
        staff_ids = []
        for i, (name, role_str, dept) in enumerate(STAFF_DATA):
            sid = str(uuid.uuid4())
            staff_ids.append(sid)
            db.add(Staff(
                id=sid,
                employee_id=f"EMP-{1001 + i}",
                name=name,
                role=StaffRole(role_str),
                department=dept,
                is_active=True,
            ))
        await db.flush()
        print(f"  Created {len(staff_ids)} staff members")

        # ── Dispensers ───────────────────────────────────────────────────
        for i, or_num in enumerate(OR_NUMBERS):
            disp_code = f"DISP-{or_num}-A"
            db.add(Dispenser(
                id=str(uuid.uuid4()),
                dispenser_id=disp_code,
                or_number=or_num,
                location_description=f"{or_num} Entry Wall",
                dispenser_type="WALL_MOUNT",
                status="ACTIVE",
            ))
            level = random.choice([95, 78, 45, 12]) if i < 4 else random.randint(20, 90)
            status = "OK" if level > 50 else "WARNING" if level > 25 else "LOW"
            db.add(DispenserStatus(
                dispenser_id=disp_code,
                level_percent=level,
                status=status,
                battery_percent=random.randint(60, 100),
            ))
        await db.flush()
        print(f"  Created {len(OR_NUMBERS)} dispensers")

        # ── Cases ────────────────────────────────────────────────────────
        all_case_ids = []

        # Completed cases (past 7 days)
        for i in range(NUM_COMPLETED_CASES):
            proc = PROCEDURES[i % len(PROCEDURES)]
            days_ago = random.randint(1, 7)
            start = now - timedelta(days=days_ago, hours=random.randint(6, 14))
            duration_hrs = proc[3] + random.uniform(-0.5, 1.0)
            end = start + timedelta(hours=duration_hrs)

            case_id = str(uuid.uuid4())
            all_case_ids.append(case_id)
            db.add(SurgicalCase(
                id=case_id,
                or_number=OR_NUMBERS[i % len(OR_NUMBERS)],
                start_time=start,
                end_time=end,
                procedure_type=proc[0],
                procedure_code=proc[1],
                surgeon_id=staff_ids[i % 2],
                patient_id=f"PAT-{1000 + i}",
                wound_class=WoundClass(proc[2]),
                expected_duration_hrs=proc[3],
                actual_duration_hrs=round(duration_hrs, 2),
                complexity_score=int(proc[4]),
                implant_flag=random.random() > 0.6,
                emergency_flag=False,
                status=CaseStatus.COMPLETED,
            ))

        # Active cases (right now)
        for i in range(NUM_ACTIVE_CASES):
            proc = PROCEDURES[(NUM_COMPLETED_CASES + i) % len(PROCEDURES)]
            start = now - timedelta(hours=random.uniform(0.5, 2.0))
            case_id = str(uuid.uuid4())
            all_case_ids.append(case_id)
            db.add(SurgicalCase(
                id=case_id,
                or_number=OR_NUMBERS[i % len(OR_NUMBERS)],
                start_time=start,
                procedure_type=proc[0],
                procedure_code=proc[1],
                surgeon_id=staff_ids[i % 2],
                patient_id=f"PAT-{2000 + i}",
                wound_class=WoundClass(proc[2]),
                expected_duration_hrs=proc[3],
                complexity_score=int(proc[4]),
                implant_flag=random.random() > 0.5,
                emergency_flag=False,
                status=CaseStatus.IN_PROGRESS,
            ))

        # Scheduled case
        case_id = str(uuid.uuid4())
        all_case_ids.append(case_id)
        db.add(SurgicalCase(
            id=case_id,
            or_number="OR-4",
            start_time=now + timedelta(hours=2),
            procedure_type="ACL Reconstruction",
            procedure_code="CPT-29888",
            surgeon_id=staff_ids[0],
            patient_id="PAT-3000",
            wound_class=WoundClass.CLEAN,
            expected_duration_hrs=2.0,
            complexity_score=6,
            implant_flag=True,
            emergency_flag=False,
            status=CaseStatus.SCHEDULED,
        ))

        await db.flush()
        print(f"  Created {len(all_case_ids)} cases ({NUM_COMPLETED_CASES} completed, {NUM_ACTIVE_CASES} active, {NUM_SCHEDULED_CASES} scheduled)")

        # ── Risk Scores ──────────────────────────────────────────────────
        for case_id in all_case_ids:
            score = random.randint(15, 85)
            if score <= 25:
                level = RiskLevel.LOW
            elif score <= 50:
                level = RiskLevel.MODERATE
            elif score <= 75:
                level = RiskLevel.HIGH
            else:
                level = RiskLevel.CRITICAL

            wound = random.choice(["CLEAN", "CLEAN_CONTAMINATED"])
            duration_risk = round(random.uniform(1.0, 5.0), 1)
            db.add(RiskScore(
                case_id=case_id,
                score=score,
                risk_level=level,
                factors=[
                    f"Wound class: {wound} (+{random.randint(0, 15)})",
                    f"Extended duration: {duration_risk}hrs (+{random.randint(0, 10)})",
                ],
                recommendations=[
                    "Ensure hand hygiene compliance at OR entry",
                    "Monitor sterile field integrity",
                    "Verify instrument sterility",
                ],
                model_version="risk-v1.0",
            ))
        await db.flush()

        # ── Entry/Exit Events ────────────────────────────────────────────
        total_entries = 0
        for case_id in all_case_ids[:NUM_COMPLETED_CASES + NUM_ACTIVE_CASES]:
            n_entries = random.randint(*ENTRIES_PER_CASE)
            for j in range(n_entries):
                compliant = random.random() < COMPLIANCE_RATE
                timestamp = now - timedelta(
                    days=random.randint(0, 5),
                    hours=random.randint(0, 8),
                    minutes=random.randint(0, 59),
                )
                db.add(EntryExitEvent(
                    id=str(uuid.uuid4()),
                    case_id=case_id,
                    event_type="ENTRY",
                    person_track_id=random.randint(1, 20),
                    staff_id=random.choice(staff_ids),
                    timestamp=timestamp,
                    compliant=compliant,
                ))
                total_entries += 1

                # Matching exit
                db.add(EntryExitEvent(
                    id=str(uuid.uuid4()),
                    case_id=case_id,
                    event_type="EXIT",
                    person_track_id=random.randint(1, 20),
                    staff_id=random.choice(staff_ids),
                    timestamp=timestamp + timedelta(minutes=random.randint(5, 90)),
                    compliant=True,
                ))
        await db.flush()
        print(f"  Created {total_entries} entry events + matching exits")

        # ── Touch Events ─────────────────────────────────────────────────
        total_touches = 0
        for case_id in all_case_ids[:NUM_COMPLETED_CASES + NUM_ACTIVE_CASES]:
            n_touches = random.randint(*TOUCH_EVENTS_PER_CASE)
            for _ in range(n_touches):
                zone = Zone(random.choice(ZONES))
                state_before = random.choice([PersonState.CLEAN, PersonState.UNKNOWN, PersonState.POTENTIALLY_CONTAMINATED])
                if zone in (Zone.CRITICAL, Zone.STERILE) and state_before != PersonState.CLEAN:
                    state_after = PersonState.CONTAMINATED
                else:
                    state_after = state_before

                db.add(TouchEvent(
                    id=str(uuid.uuid4()),
                    case_id=case_id,
                    person_track_id=random.randint(1, 20),
                    zone=zone,
                    hand=random.choice(["LEFT", "RIGHT"]),
                    person_state_before=state_before,
                    person_state_after=state_after,
                    timestamp=now - timedelta(
                        days=random.randint(0, 5),
                        hours=random.randint(0, 8),
                    ),
                ))
                total_touches += 1
        await db.flush()
        print(f"  Created {total_touches} touch events")

        # ── Alerts ───────────────────────────────────────────────────────
        total_alerts = 0
        for case_id in all_case_ids[:NUM_COMPLETED_CASES + NUM_ACTIVE_CASES]:
            n_alerts = random.randint(*NUM_ALERTS_PER_CASE)
            for _ in range(n_alerts):
                alert_type = AlertType(random.choice(ALERT_TYPES))
                severity = AlertSeverity(random.choice(ALERT_SEVERITIES))
                created_at = now - timedelta(
                    days=random.randint(0, 5),
                    hours=random.randint(0, 12),
                )
                acknowledged = random.random() > 0.4
                resolved = acknowledged and random.random() > 0.3

                db.add(Alert(
                    id=str(uuid.uuid4()),
                    case_id=case_id,
                    alert_type=alert_type,
                    severity=severity,
                    message=_alert_message(alert_type),
                    acknowledged=acknowledged,
                    acknowledged_by=random.choice(staff_ids) if acknowledged else None,
                    resolved=resolved,
                    timestamp=created_at,
                ))
                total_alerts += 1
        await db.flush()
        print(f"  Created {total_alerts} alerts")

        await db.commit()
        print("\nDemo data seeded successfully!")
        print(f"  Dashboard: http://localhost:3000")
        print(f"  API docs:  http://localhost:8000/docs")
        print(f"  Grafana:   http://localhost:3001  (admin / infectioniq)")


def _alert_message(alert_type) -> str:
    messages = {
        "CONTAMINATION": "Staff member entered sterile field without hand hygiene",
        "MISSED_HYGIENE": "OR entry without hand sanitization detected",
        "HIGH_RISK": "High-risk case: compliance rate below threshold",
        "CRITICAL_ZONE": "Unsanitized contact with critical zone detected",
    }
    return messages.get(alert_type.value if hasattr(alert_type, 'value') else alert_type, "Compliance violation detected")


if __name__ == "__main__":
    print("Seeding InfectionIQ demo data...")
    asyncio.run(seed_demo_data())
