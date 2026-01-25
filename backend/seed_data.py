"""
Seed Database with Test Data
Run: python seed_data.py
"""
import asyncio
import uuid
from datetime import datetime, timedelta
import random

# Add backend to path
import sys
sys.path.insert(0, '.')

from sqlalchemy import select
from app.core.database import async_session_maker, init_db
from app.models.models import (
    Staff, Team, TeamMember, SurgicalCase, RiskScore,
    EntryExitEvent, Alert, Dispenser, DispenserStatus,
    StaffRole, WoundClass, CaseStatus, RiskLevel, AlertType, AlertSeverity
)


async def seed_data():
    """Seed database with test data"""

    # Initialize database
    await init_db()

    async with async_session_maker() as session:
        # Check if data already exists
        result = await session.execute(select(Staff).limit(1))
        if result.scalar_one_or_none():
            print("Database already has data. Skipping seed.")
            return

        print("Seeding database...")

        # Create Staff
        staff_data = [
            {"employee_id": "DOC001", "name": "Dr. Sarah Chen", "role": StaffRole.SURGEON, "department": "General Surgery", "email": "s.chen@hospital.org"},
            {"employee_id": "DOC002", "name": "Dr. Michael Roberts", "role": StaffRole.SURGEON, "department": "Orthopedics", "email": "m.roberts@hospital.org"},
            {"employee_id": "DOC003", "name": "Dr. Emily Watson", "role": StaffRole.ANESTHESIOLOGIST, "department": "Anesthesiology", "email": "e.watson@hospital.org"},
            {"employee_id": "NRS001", "name": "Jennifer Martinez", "role": StaffRole.NURSE, "department": "OR Nursing", "email": "j.martinez@hospital.org"},
            {"employee_id": "NRS002", "name": "David Kim", "role": StaffRole.NURSE, "department": "OR Nursing", "email": "d.kim@hospital.org"},
            {"employee_id": "NRS003", "name": "Lisa Thompson", "role": StaffRole.NURSE, "department": "OR Nursing", "email": "l.thompson@hospital.org"},
            {"employee_id": "TEC001", "name": "James Wilson", "role": StaffRole.TECH, "department": "Surgical Tech", "email": "j.wilson@hospital.org"},
            {"employee_id": "TEC002", "name": "Maria Garcia", "role": StaffRole.TECH, "department": "Surgical Tech", "email": "m.garcia@hospital.org"},
            {"employee_id": "RES001", "name": "Dr. Alex Johnson", "role": StaffRole.RESIDENT, "department": "General Surgery", "email": "a.johnson@hospital.org"},
        ]

        staff_objects = []
        for data in staff_data:
            staff = Staff(id=uuid.uuid4(), **data)
            session.add(staff)
            staff_objects.append(staff)

        await session.flush()
        print(f"  Created {len(staff_objects)} staff members")

        # Create Teams
        team1 = Team(
            id=uuid.uuid4(),
            name="General Surgery Team A",
            department="General Surgery",
            lead_id=staff_objects[0].id
        )
        team2 = Team(
            id=uuid.uuid4(),
            name="Orthopedic Team B",
            department="Orthopedics",
            lead_id=staff_objects[1].id
        )
        session.add(team1)
        session.add(team2)
        await session.flush()
        print("  Created 2 teams")

        # Create Team Members
        team_members = [
            TeamMember(team_id=team1.id, staff_id=staff_objects[0].id, role_in_team="LEAD"),
            TeamMember(team_id=team1.id, staff_id=staff_objects[3].id, role_in_team="MEMBER"),
            TeamMember(team_id=team1.id, staff_id=staff_objects[6].id, role_in_team="MEMBER"),
            TeamMember(team_id=team2.id, staff_id=staff_objects[1].id, role_in_team="LEAD"),
            TeamMember(team_id=team2.id, staff_id=staff_objects[4].id, role_in_team="MEMBER"),
            TeamMember(team_id=team2.id, staff_id=staff_objects[7].id, role_in_team="MEMBER"),
        ]
        for tm in team_members:
            session.add(tm)
        print("  Created team memberships")

        # Create Surgical Cases
        procedures = [
            ("Appendectomy", "APX001", WoundClass.CLEAN_CONTAMINATED, 1.5),
            ("Hip Replacement", "HIP001", WoundClass.CLEAN, 3.0),
            ("Cholecystectomy", "CHO001", WoundClass.CLEAN_CONTAMINATED, 2.0),
            ("Knee Arthroscopy", "KNE001", WoundClass.CLEAN, 1.0),
            ("Hernia Repair", "HER001", WoundClass.CLEAN, 1.5),
        ]

        cases = []
        now = datetime.utcnow()

        # Active case
        active_case = SurgicalCase(
            id=uuid.uuid4(),
            or_number="OR-1",
            start_time=now - timedelta(hours=1),
            procedure_type="Laparoscopic Cholecystectomy",
            procedure_code="CHO002",
            surgeon_id=staff_objects[0].id,
            team_id=team1.id,
            patient_id="PAT12345",
            wound_class=WoundClass.CLEAN_CONTAMINATED,
            expected_duration_hrs=2.0,
            complexity_score=6,
            implant_flag=False,
            emergency_flag=False,
            status=CaseStatus.IN_PROGRESS
        )
        session.add(active_case)
        cases.append(active_case)

        # Completed cases (last 7 days)
        for i, (proc_name, proc_code, wound, duration) in enumerate(procedures):
            days_ago = i + 1
            case = SurgicalCase(
                id=uuid.uuid4(),
                or_number=f"OR-{(i % 3) + 1}",
                start_time=now - timedelta(days=days_ago, hours=random.randint(8, 14)),
                end_time=now - timedelta(days=days_ago, hours=random.randint(8, 14)) + timedelta(hours=duration),
                procedure_type=proc_name,
                procedure_code=proc_code,
                surgeon_id=staff_objects[i % 2].id,
                team_id=team1.id if i % 2 == 0 else team2.id,
                patient_id=f"PAT{10000 + i}",
                wound_class=wound,
                expected_duration_hrs=duration,
                actual_duration_hrs=duration + random.uniform(-0.5, 0.5),
                complexity_score=random.randint(3, 8),
                implant_flag=i == 1,  # Hip replacement has implant
                emergency_flag=False,
                status=CaseStatus.COMPLETED,
                outcome="SUCCESSFUL"
            )
            session.add(case)
            cases.append(case)

        await session.flush()
        print(f"  Created {len(cases)} surgical cases")

        # Create Risk Scores
        for case in cases:
            risk_score = random.randint(15, 65)
            if risk_score < 25:
                risk_level = RiskLevel.LOW
            elif risk_score < 50:
                risk_level = RiskLevel.MODERATE
            elif risk_score < 75:
                risk_level = RiskLevel.HIGH
            else:
                risk_level = RiskLevel.CRITICAL

            rs = RiskScore(
                case_id=case.id,
                score=risk_score,
                risk_level=risk_level,
                factors=["Wound class", "Procedure duration"],
                recommendations=["Standard protocol", "Monitor hygiene compliance"],
                model_version="1.0-rules"
            )
            session.add(rs)
        print("  Created risk scores")

        # Create Entry/Exit Events for active case
        for i, staff in enumerate(staff_objects[:5]):
            compliant = random.random() > 0.15  # 85% compliance rate
            event = EntryExitEvent(
                id=uuid.uuid4(),
                case_id=active_case.id,
                staff_id=staff.id,
                person_track_id=i + 1,
                event_type="ENTRY",
                timestamp=active_case.start_time + timedelta(minutes=i * 2),
                compliant=compliant,
                sanitize_method="SANITIZER" if compliant else "NONE",
                sanitize_duration_sec=3.5 if compliant else 0,
                confidence=0.95
            )
            session.add(event)
        print("  Created entry/exit events")

        # Create Alerts
        alert1 = Alert(
            id=uuid.uuid4(),
            case_id=active_case.id,
            staff_id=staff_objects[4].id,
            alert_type=AlertType.MISSED_HYGIENE,
            severity=AlertSeverity.MEDIUM,
            message="Staff member entered without sanitizing",
            acknowledged=False,
            resolved=False,
            timestamp=active_case.start_time + timedelta(minutes=8)
        )
        session.add(alert1)

        alert2 = Alert(
            id=uuid.uuid4(),
            case_id=cases[1].id,
            alert_type=AlertType.DISPENSER_LOW,
            severity=AlertSeverity.LOW,
            message="Dispenser in OR-1 is running low (25%)",
            acknowledged=True,
            acknowledged_by=staff_objects[3].id,
            acknowledged_at=now - timedelta(days=1),
            resolved=True,
            resolved_at=now - timedelta(days=1),
            timestamp=now - timedelta(days=1, hours=2)
        )
        session.add(alert2)
        print("  Created alerts")

        # Create Dispensers
        dispensers_data = [
            {"dispenser_id": "DISP-OR1-A", "or_number": "OR-1", "location_description": "Near entrance", "dispenser_type": "WALL_MOUNT"},
            {"dispenser_id": "DISP-OR1-B", "or_number": "OR-1", "location_description": "Near surgical table", "dispenser_type": "WALL_MOUNT"},
            {"dispenser_id": "DISP-OR2-A", "or_number": "OR-2", "location_description": "Near entrance", "dispenser_type": "WALL_MOUNT"},
            {"dispenser_id": "DISP-OR3-A", "or_number": "OR-3", "location_description": "Near entrance", "dispenser_type": "STAND"},
        ]

        dispensers = []
        for data in dispensers_data:
            disp = Dispenser(
                id=uuid.uuid4(),
                capacity_ml=1200,
                installed_at=now - timedelta(days=90),
                status="ACTIVE",
                **data
            )
            session.add(disp)
            dispensers.append(disp)

        await session.flush()
        print("  Created dispensers")

        # Create Dispenser Status
        status_data = [
            {"level_percent": 75.0, "status": "OK", "dispenses_today": 45},
            {"level_percent": 35.0, "status": "WARNING", "dispenses_today": 62},
            {"level_percent": 88.0, "status": "OK", "dispenses_today": 28},
            {"level_percent": 15.0, "status": "LOW", "dispenses_today": 71},
        ]

        for disp, status in zip(dispensers, status_data):
            ds = DispenserStatus(
                dispenser_id=disp.dispenser_id,
                level_percent=status["level_percent"],
                level_ml=status["level_percent"] * 12,  # 1200ml capacity
                status=status["status"],
                dispenses_today=status["dispenses_today"],
                volume_today_ml=status["dispenses_today"] * 2.5,
                avg_volume_per_dispense=2.5,
                last_dispense_time=now - timedelta(minutes=random.randint(5, 60)),
                battery_percent=95.0,
                cartridge_type="Alcohol-based gel",
                cartridge_installed_at=now - timedelta(days=14),
                cartridge_expiration_date=now + timedelta(days=180),
                days_until_expiration=180,
                last_updated=now
            )
            session.add(ds)
        print("  Created dispenser statuses")

        await session.commit()
        print("\nDatabase seeded successfully!")


if __name__ == "__main__":
    asyncio.run(seed_data())
