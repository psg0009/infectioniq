"""
Case Service - Business logic for surgical cases
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import logging

from app.models import SurgicalCase, RiskScore, EntryExitEvent, TouchEvent, Alert
from app.schemas import (
    CaseCreate, CaseUpdate, CaseResponse, CaseWithRiskResponse,
    CaseComplianceResponse, RiskLevel, CaseStatus
)
from app.services.risk_service import RiskService
from app.core.redis import RedisPubSub, RedisCache

logger = logging.getLogger(__name__)


class CaseService:
    """Service for surgical case operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.risk_service = RiskService(db)
    
    async def create_case(self, case_data: CaseCreate) -> CaseWithRiskResponse:
        """Create a new surgical case and calculate risk score"""
        
        # Create the case
        case = SurgicalCase(
            or_number=case_data.or_number,
            start_time=case_data.start_time,
            procedure_type=case_data.procedure_type,
            procedure_code=case_data.procedure_code,
            surgeon_id=case_data.surgeon_id,
            team_id=case_data.team_id,
            patient_id=case_data.patient_id,
            wound_class=case_data.wound_class,
            expected_duration_hrs=case_data.expected_duration_hrs,
            complexity_score=case_data.complexity_score,
            implant_flag=case_data.implant_flag,
            emergency_flag=case_data.emergency_flag,
            status=CaseStatus.SCHEDULED
        )
        
        self.db.add(case)
        await self.db.flush()
        
        # Calculate risk score
        risk_prediction = await self.risk_service.predict_risk(case)
        
        # Store risk score
        risk_score = RiskScore(
            case_id=case.id,
            score=risk_prediction["score"],
            risk_level=risk_prediction["risk_level"],
            factors=risk_prediction["factors"],
            recommendations=risk_prediction["recommendations"],
            model_version=risk_prediction["model_version"]
        )
        self.db.add(risk_score)
        
        await self.db.commit()
        await self.db.refresh(case)
        
        # Cache active case for the OR
        await RedisCache.set_active_case(case.or_number, {
            "case_id": str(case.id),
            "or_number": case.or_number,
            "procedure_type": case.procedure_type,
            "status": case.status.value,
            "start_time": case.start_time.isoformat()
        })
        
        # Build response
        response = CaseWithRiskResponse(
            id=case.id,
            or_number=case.or_number,
            start_time=case.start_time,
            end_time=case.end_time,
            procedure_type=case.procedure_type,
            procedure_code=case.procedure_code,
            surgeon_id=case.surgeon_id,
            team_id=case.team_id,
            patient_id=case.patient_id,
            wound_class=case.wound_class,
            expected_duration_hrs=case.expected_duration_hrs,
            actual_duration_hrs=case.actual_duration_hrs,
            complexity_score=case.complexity_score,
            implant_flag=case.implant_flag,
            emergency_flag=case.emergency_flag,
            status=case.status,
            outcome=case.outcome,
            created_at=case.created_at,
            risk_score=risk_prediction
        )
        
        logger.info(f"Created case {case.id} with risk score {risk_prediction['score']}")
        
        return response
    
    async def get_case(self, case_id: UUID) -> Optional[CaseWithRiskResponse]:
        """Get case by ID with risk score"""
        
        result = await self.db.execute(
            select(SurgicalCase)
            .options(selectinload(SurgicalCase.risk_score))
            .where(SurgicalCase.id == case_id)
        )
        case = result.scalar_one_or_none()
        
        if not case:
            return None
        
        risk_score_response = None
        if case.risk_score:
            risk_score_response = {
                "score": case.risk_score.score,
                "risk_level": case.risk_score.risk_level,
                "factors": case.risk_score.factors,
                "recommendations": case.risk_score.recommendations,
                "model_version": case.risk_score.model_version,
                "created_at": case.risk_score.created_at
            }
        
        return CaseWithRiskResponse(
            id=case.id,
            or_number=case.or_number,
            start_time=case.start_time,
            end_time=case.end_time,
            procedure_type=case.procedure_type,
            procedure_code=case.procedure_code,
            surgeon_id=case.surgeon_id,
            team_id=case.team_id,
            patient_id=case.patient_id,
            wound_class=case.wound_class,
            expected_duration_hrs=case.expected_duration_hrs,
            actual_duration_hrs=case.actual_duration_hrs,
            complexity_score=case.complexity_score,
            implant_flag=case.implant_flag,
            emergency_flag=case.emergency_flag,
            status=case.status,
            outcome=case.outcome,
            created_at=case.created_at,
            risk_score=risk_score_response
        )
    
    async def update_case(self, case_id: UUID, update_data: CaseUpdate) -> Optional[CaseResponse]:
        """Update a surgical case"""
        
        result = await self.db.execute(
            select(SurgicalCase).where(SurgicalCase.id == case_id)
        )
        case = result.scalar_one_or_none()
        
        if not case:
            return None
        
        # Update fields
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(case, field, value)
        
        # If ending case, calculate actual duration
        if update_data.end_time and case.start_time:
            duration = (update_data.end_time - case.start_time).total_seconds() / 3600
            case.actual_duration_hrs = round(duration, 2)
        
        await self.db.commit()
        await self.db.refresh(case)
        
        return CaseResponse.model_validate(case)
    
    async def get_active_cases(self) -> List[CaseWithRiskResponse]:
        """Get all active (in progress) cases"""
        
        result = await self.db.execute(
            select(SurgicalCase)
            .options(selectinload(SurgicalCase.risk_score))
            .where(SurgicalCase.status == CaseStatus.IN_PROGRESS)
            .order_by(SurgicalCase.start_time.desc())
        )
        cases = result.scalars().all()
        
        return [
            CaseWithRiskResponse(
                id=case.id,
                or_number=case.or_number,
                start_time=case.start_time,
                end_time=case.end_time,
                procedure_type=case.procedure_type,
                procedure_code=case.procedure_code,
                surgeon_id=case.surgeon_id,
                team_id=case.team_id,
                patient_id=case.patient_id,
                wound_class=case.wound_class,
                expected_duration_hrs=case.expected_duration_hrs,
                actual_duration_hrs=case.actual_duration_hrs,
                complexity_score=case.complexity_score,
                implant_flag=case.implant_flag,
                emergency_flag=case.emergency_flag,
                status=case.status,
                outcome=case.outcome,
                created_at=case.created_at,
                risk_score={
                    "score": case.risk_score.score,
                    "risk_level": case.risk_score.risk_level,
                    "factors": case.risk_score.factors,
                    "recommendations": case.risk_score.recommendations,
                    "model_version": case.risk_score.model_version,
                    "created_at": case.risk_score.created_at
                } if case.risk_score else None
            )
            for case in cases
        ]
    
    async def get_case_compliance(self, case_id: UUID) -> Optional[CaseComplianceResponse]:
        """Get compliance statistics for a case"""
        
        # Get entry/exit events
        entry_result = await self.db.execute(
            select(EntryExitEvent)
            .where(EntryExitEvent.case_id == case_id)
            .where(EntryExitEvent.event_type == "ENTRY")
        )
        entries = entry_result.scalars().all()
        
        total_entries = len(entries)
        compliant_entries = sum(1 for e in entries if e.compliant)
        
        # Get touch events
        touch_result = await self.db.execute(
            select(func.count(TouchEvent.id))
            .where(TouchEvent.case_id == case_id)
        )
        total_touches = touch_result.scalar() or 0
        
        # Get contamination events
        contam_result = await self.db.execute(
            select(func.count(TouchEvent.id))
            .where(TouchEvent.case_id == case_id)
            .where(TouchEvent.person_state_after.in_(["CONTAMINATED", "POTENTIALLY_CONTAMINATED"]))
        )
        contamination_events = contam_result.scalar() or 0
        
        # Get alerts
        alert_result = await self.db.execute(
            select(func.count(Alert.id))
            .where(Alert.case_id == case_id)
        )
        alerts_count = alert_result.scalar() or 0
        
        # Calculate compliance rate
        compliance_rate = compliant_entries / total_entries if total_entries > 0 else 1.0
        
        # Staff compliance breakdown
        staff_compliance = []
        staff_entries = {}
        for entry in entries:
            staff_id = str(entry.staff_id) if entry.staff_id else f"person_{entry.person_track_id}"
            if staff_id not in staff_entries:
                staff_entries[staff_id] = {"total": 0, "compliant": 0}
            staff_entries[staff_id]["total"] += 1
            if entry.compliant:
                staff_entries[staff_id]["compliant"] += 1
        
        for staff_id, counts in staff_entries.items():
            staff_compliance.append({
                "staff_id": staff_id,
                "total_entries": counts["total"],
                "compliant_entries": counts["compliant"],
                "compliance_rate": counts["compliant"] / counts["total"] if counts["total"] > 0 else 1.0
            })
        
        return CaseComplianceResponse(
            case_id=case_id,
            overall_compliance_rate=compliance_rate,
            total_entries=total_entries,
            compliant_entries=compliant_entries,
            total_touches=total_touches,
            contamination_events=contamination_events,
            alerts_count=alerts_count,
            staff_compliance=staff_compliance
        )
    
    async def start_case(self, case_id: UUID) -> Optional[CaseResponse]:
        """Start a surgical case (change status to IN_PROGRESS)"""
        
        result = await self.db.execute(
            select(SurgicalCase).where(SurgicalCase.id == case_id)
        )
        case = result.scalar_one_or_none()
        
        if not case:
            return None
        
        case.status = CaseStatus.IN_PROGRESS
        case.start_time = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(case)
        
        # Update cache
        await RedisCache.set_active_case(case.or_number, {
            "case_id": str(case.id),
            "or_number": case.or_number,
            "procedure_type": case.procedure_type,
            "status": case.status.value,
            "start_time": case.start_time.isoformat()
        })
        
        # Publish event
        await RedisPubSub.publish_or_event(case.or_number, "CASE_STARTED", {
            "case_id": str(case.id),
            "procedure_type": case.procedure_type,
            "start_time": case.start_time.isoformat()
        })
        
        return CaseResponse.model_validate(case)
    
    async def end_case(self, case_id: UUID, outcome: Optional[str] = None) -> Optional[CaseResponse]:
        """End a surgical case"""
        
        result = await self.db.execute(
            select(SurgicalCase).where(SurgicalCase.id == case_id)
        )
        case = result.scalar_one_or_none()
        
        if not case:
            return None
        
        case.status = CaseStatus.COMPLETED
        case.end_time = datetime.utcnow()
        if outcome:
            case.outcome = outcome
        
        # Calculate actual duration
        if case.start_time:
            duration = (case.end_time - case.start_time).total_seconds() / 3600
            case.actual_duration_hrs = round(duration, 2)
        
        await self.db.commit()
        await self.db.refresh(case)
        
        # Clear active case cache
        await RedisCache.delete(f"active_case:{case.or_number}")
        
        # Publish event
        await RedisPubSub.publish_or_event(case.or_number, "CASE_ENDED", {
            "case_id": str(case.id),
            "end_time": case.end_time.isoformat(),
            "duration_hrs": case.actual_duration_hrs
        })
        
        return CaseResponse.model_validate(case)
