"""
Risk Prediction Service - ML-based infection risk scoring
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy import select, func, Integer
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np
import logging

from app.models import SurgicalCase, Staff, Team, EntryExitEvent, InfectionOutcome
from app.core.enums import RiskLevel
from app.config import settings

logger = logging.getLogger(__name__)


class RiskService:
    """Service for risk prediction"""
    
    # Feature weights (simplified - in production, load from trained model)
    FEATURE_WEIGHTS = {
        "team_infection_count_90d": 0.18,
        "team_compliance_7d": 0.15,
        "estimated_duration_hrs": 0.12,
        "surgeon_compliance_avg": 0.11,
        "wound_class": 0.10,
        "complexity_score": 0.08,
        "implant_flag": 0.07,
        "team_violation_rate": 0.06,
        "new_team_member_flag": 0.05,
        "is_night_shift": 0.04,
        "emergency_flag": 0.02,
        "is_weekend": 0.02
    }
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def predict_risk(self, case: SurgicalCase) -> Dict[str, Any]:
        """
        Predict infection risk for a surgical case
        Returns score (0-100), risk level, contributing factors, and recommendations
        """
        
        # Extract features
        features = await self._extract_features(case)
        
        # Calculate risk score
        score = self._calculate_score(features)
        
        # Determine risk level
        risk_level = self._get_risk_level(score)
        
        # Get contributing factors
        factors = self._get_contributing_factors(features)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(factors, risk_level)
        
        return {
            "score": score,
            "risk_level": risk_level.value,
            "factors": factors,
            "recommendations": recommendations,
            "model_version": "1.0.0"
        }
    
    async def _extract_features(self, case: SurgicalCase) -> Dict[str, float]:
        """Extract all features for risk prediction"""
        
        features = {}
        
        # Team history features
        if case.team_id:
            team_features = await self._get_team_features(case.team_id)
            features.update(team_features)
        else:
            # Default values if no team
            features["team_compliance_7d"] = 0.9
            features["team_compliance_30d"] = 0.9
            features["team_infection_count_90d"] = 0
            features["team_violation_rate"] = 0.05
            features["new_team_member_flag"] = 0
        
        # Surgeon compliance
        if case.surgeon_id:
            surgeon_compliance = await self._get_staff_compliance(case.surgeon_id)
            features["surgeon_compliance_avg"] = surgeon_compliance
        else:
            features["surgeon_compliance_avg"] = 0.9
        
        # Surgery context features
        features["estimated_duration_hrs"] = case.expected_duration_hrs or 2.0
        features["complexity_score"] = case.complexity_score or 3
        features["implant_flag"] = 1 if case.implant_flag else 0
        features["emergency_flag"] = 1 if case.emergency_flag else 0
        
        # Wound class encoding
        wound_class_risk = {
            "CLEAN": 0.0,
            "CLEAN_CONTAMINATED": 0.25,
            "CONTAMINATED": 0.5,
            "DIRTY": 0.75,
            "UNKNOWN": 0.25
        }
        wound_class = case.wound_class.value if case.wound_class else "UNKNOWN"
        features["wound_class"] = wound_class_risk.get(wound_class, 0.25)
        
        # Temporal features
        start_hour = case.start_time.hour
        features["is_night_shift"] = 1 if start_hour >= 19 or start_hour <= 6 else 0
        features["is_weekend"] = 1 if case.start_time.weekday() >= 5 else 0
        
        return features
    
    async def _get_team_features(self, team_id: UUID) -> Dict[str, float]:
        """Get historical features for a team"""
        
        now = datetime.utcnow()
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)
        ninety_days_ago = now - timedelta(days=90)
        
        # Get team member IDs
        team_result = await self.db.execute(
            select(Team).where(Team.id == team_id)
        )
        team = team_result.scalar_one_or_none()
        
        if not team:
            return {
                "team_compliance_7d": 0.9,
                "team_compliance_30d": 0.9,
                "team_infection_count_90d": 0,
                "team_violation_rate": 0.05,
                "new_team_member_flag": 0
            }
        
        # Get compliance rate (last 7 days)
        compliance_7d_result = await self.db.execute(
            select(
                func.count(EntryExitEvent.id).label("total"),
                func.sum(func.cast(EntryExitEvent.compliant, Integer)).label("compliant")
            )
            .where(EntryExitEvent.timestamp >= seven_days_ago)
            .where(EntryExitEvent.event_type == "ENTRY")
        )
        compliance_7d = compliance_7d_result.one()
        
        team_compliance_7d = compliance_7d.compliant / compliance_7d.total if compliance_7d.total > 0 else 0.9
        
        # Get compliance rate (last 30 days) 
        compliance_30d_result = await self.db.execute(
            select(
                func.count(EntryExitEvent.id).label("total"),
                func.sum(func.cast(EntryExitEvent.compliant, Integer)).label("compliant")
            )
            .where(EntryExitEvent.timestamp >= thirty_days_ago)
            .where(EntryExitEvent.event_type == "ENTRY")
        )
        compliance_30d = compliance_30d_result.one()
        
        team_compliance_30d = compliance_30d.compliant / compliance_30d.total if compliance_30d.total > 0 else 0.9
        
        # Get infection count (last 90 days)
        infection_result = await self.db.execute(
            select(func.count(InfectionOutcome.id))
            .join(SurgicalCase)
            .where(SurgicalCase.team_id == team_id)
            .where(InfectionOutcome.infection_detected == True)
            .where(InfectionOutcome.created_at >= ninety_days_ago)
        )
        infection_count = infection_result.scalar() or 0
        
        # Calculate violation rate
        violation_rate = 1 - team_compliance_30d
        
        return {
            "team_compliance_7d": team_compliance_7d,
            "team_compliance_30d": team_compliance_30d,
            "team_infection_count_90d": infection_count,
            "team_violation_rate": violation_rate,
            "new_team_member_flag": 0  # Would need team membership history
        }
    
    async def _get_staff_compliance(self, staff_id: UUID) -> float:
        """Get compliance rate for a staff member"""
        
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        result = await self.db.execute(
            select(
                func.count(EntryExitEvent.id).label("total"),
                func.sum(func.cast(EntryExitEvent.compliant, Integer)).label("compliant")
            )
            .where(EntryExitEvent.staff_id == staff_id)
            .where(EntryExitEvent.timestamp >= thirty_days_ago)
            .where(EntryExitEvent.event_type == "ENTRY")
        )
        data = result.one()
        
        if data.total > 0:
            return data.compliant / data.total
        return 0.9  # Default if no history
    
    def _calculate_score(self, features: Dict[str, float]) -> int:
        """Calculate risk score from features"""
        
        score = 0.0
        
        # Base score from weighted features
        for feature, weight in self.FEATURE_WEIGHTS.items():
            if feature in features:
                value = features[feature]
                
                # Normalize and convert to risk contribution
                if feature in ["team_compliance_7d", "team_compliance_30d", "surgeon_compliance_avg"]:
                    # Lower compliance = higher risk
                    contribution = (1 - value) * weight * 100
                elif feature == "team_infection_count_90d":
                    # More infections = higher risk
                    contribution = min(value * 10, 30) * weight * 100 / 30
                elif feature == "estimated_duration_hrs":
                    # Longer surgery = higher risk
                    contribution = min(value / 8, 1) * weight * 100
                elif feature == "complexity_score":
                    # Higher complexity = higher risk
                    contribution = (value / 5) * weight * 100
                elif feature == "wound_class":
                    # Higher wound class risk = higher overall risk
                    contribution = value * weight * 100
                else:
                    # Binary features
                    contribution = value * weight * 100
                
                score += contribution
        
        # Ensure score is between 0 and 100
        score = max(0, min(100, int(score)))
        
        return score
    
    def _get_risk_level(self, score: int) -> RiskLevel:
        """Convert score to risk level"""
        
        if score <= 25:
            return RiskLevel.LOW
        elif score <= 50:
            return RiskLevel.MODERATE
        elif score <= 75:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL
    
    def _get_contributing_factors(self, features: Dict[str, float]) -> List[Dict[str, Any]]:
        """Get top contributing factors"""
        
        factors = []
        
        # Calculate contribution of each factor
        contributions = []
        for feature, weight in self.FEATURE_WEIGHTS.items():
            if feature in features:
                value = features[feature]
                
                # Calculate how much this feature contributes to risk
                if feature in ["team_compliance_7d", "team_compliance_30d", "surgeon_compliance_avg"]:
                    contribution = (1 - value) * weight
                    if value < 0.85:
                        factors.append({
                            "name": feature,
                            "value": value,
                            "weight": round(weight, 2),
                            "description": f"Low compliance rate: {value*100:.1f}%"
                        })
                elif feature == "team_infection_count_90d" and value > 0:
                    factors.append({
                        "name": feature,
                        "value": value,
                        "weight": round(weight, 2),
                        "description": f"Team has {int(value)} recent infection(s)"
                    })
                elif feature == "estimated_duration_hrs" and value > 3:
                    factors.append({
                        "name": feature,
                        "value": value,
                        "weight": round(weight, 2),
                        "description": f"Long surgery duration: {value:.1f} hours"
                    })
                elif feature == "complexity_score" and value >= 4:
                    factors.append({
                        "name": feature,
                        "value": value,
                        "weight": round(weight, 2),
                        "description": f"High complexity surgery (score: {int(value)}/5)"
                    })
                elif feature == "wound_class" and value > 0.25:
                    factors.append({
                        "name": feature,
                        "value": value,
                        "weight": round(weight, 2),
                        "description": "Higher wound classification increases risk"
                    })
                elif feature == "implant_flag" and value == 1:
                    factors.append({
                        "name": feature,
                        "value": value,
                        "weight": round(weight, 2),
                        "description": "Implant surgery - elevated infection risk"
                    })
                elif feature == "emergency_flag" and value == 1:
                    factors.append({
                        "name": feature,
                        "value": value,
                        "weight": round(weight, 2),
                        "description": "Emergency surgery - less prep time"
                    })
                elif feature == "is_night_shift" and value == 1:
                    factors.append({
                        "name": feature,
                        "value": value,
                        "weight": round(weight, 2),
                        "description": "Night shift surgery"
                    })
        
        # Sort by weight and return top factors
        factors.sort(key=lambda x: x["weight"], reverse=True)
        return factors[:5]  # Return top 5 factors
    
    def _generate_recommendations(self, factors: List[Dict], risk_level: RiskLevel) -> List[str]:
        """Generate recommendations based on risk factors"""
        
        recommendations = []
        
        # General recommendations based on risk level
        if risk_level == RiskLevel.CRITICAL:
            recommendations.append("Consider dedicated compliance observer for this case")
            recommendations.append("Pre-surgery hygiene briefing recommended")
        elif risk_level == RiskLevel.HIGH:
            recommendations.append("Enhanced monitoring recommended")
            recommendations.append("Ensure adequate sanitizer supplies")
        
        # Factor-specific recommendations
        for factor in factors:
            name = factor["name"]
            
            if name in ["team_compliance_7d", "team_compliance_30d"]:
                recommendations.append("Review hand hygiene protocols with team")
            elif name == "team_infection_count_90d":
                recommendations.append("Review recent infection cases for patterns")
            elif name == "estimated_duration_hrs":
                recommendations.append("Plan for additional sanitization breaks during long surgery")
            elif name == "complexity_score":
                recommendations.append("Ensure experienced team members present")
            elif name == "implant_flag":
                recommendations.append("Strict sterile technique enforcement for implant surgery")
            elif name == "emergency_flag":
                recommendations.append("Verify all hand hygiene steps despite time pressure")
        
        # Deduplicate
        recommendations = list(dict.fromkeys(recommendations))
        
        return recommendations[:5]  # Return top 5 recommendations
