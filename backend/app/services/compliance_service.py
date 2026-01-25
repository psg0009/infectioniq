"""
Compliance Service - Business logic for compliance tracking
"""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.models import EntryExitEvent, TouchEvent, Alert, SurgicalCase
from app.models.models import PersonState, Zone, AlertType, AlertSeverity
from app.schemas import (
    EntryEventCreate, TouchEventCreate, 
    EntryExitEventResponse, TouchEventWithStateResponse,
    StateChangeResponse, AlertResponse
)
from app.core.redis import RedisPubSub, RedisCache
from app.config import settings

logger = logging.getLogger(__name__)


class ComplianceService:
    """Service for compliance event tracking"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def record_entry(self, event_data: EntryEventCreate) -> Dict[str, Any]:
        """Record an entry event with compliance status"""
        
        # Create entry event
        entry_event = EntryExitEvent(
            case_id=event_data.case_id,
            staff_id=event_data.staff_id,
            person_track_id=event_data.person_track_id,
            event_type="ENTRY",
            timestamp=event_data.timestamp,
            compliant=event_data.compliant,
            sanitize_method=event_data.sanitize_method,
            sanitize_duration_sec=event_data.sanitize_duration_sec,
            sanitize_volume_ml=event_data.sanitize_volume_ml,
            confidence=event_data.confidence
        )
        
        self.db.add(entry_event)
        await self.db.flush()
        
        # Determine initial person state
        person_id = event_data.person_track_id or hash(str(event_data.staff_id))
        if event_data.compliant:
            initial_state = PersonState.CLEAN
        else:
            initial_state = PersonState.DIRTY
        
        # Cache person state
        await RedisCache.set_person_state(str(event_data.case_id), person_id, {
            "state": initial_state.value,
            "last_sanitize": event_data.timestamp.isoformat() if event_data.compliant else None,
            "entry_time": event_data.timestamp.isoformat(),
            "staff_id": str(event_data.staff_id) if event_data.staff_id else None
        })
        
        # Create alert if non-compliant entry
        alert = None
        if not event_data.compliant:
            alert = Alert(
                case_id=event_data.case_id,
                staff_id=event_data.staff_id,
                alert_type=AlertType.MISSED_HYGIENE,
                severity=AlertSeverity.HIGH,
                message="Entry without hand sanitization detected",
                timestamp=event_data.timestamp
            )
            self.db.add(alert)
            await self.db.flush()
            
            # Publish alert
            await RedisPubSub.publish_alert({
                "alert_id": str(alert.id),
                "case_id": str(event_data.case_id),
                "alert_type": "MISSED_HYGIENE",
                "severity": "HIGH",
                "message": alert.message,
                "timestamp": event_data.timestamp.isoformat()
            })
        
        await self.db.commit()
        
        # Publish entry event
        await RedisPubSub.publish_case_event(str(event_data.case_id), "ENTRY", {
            "event_id": str(entry_event.id),
            "staff_id": str(event_data.staff_id) if event_data.staff_id else None,
            "person_track_id": person_id,
            "compliant": event_data.compliant,
            "person_state": initial_state.value,
            "timestamp": event_data.timestamp.isoformat()
        })
        
        return {
            "event_id": entry_event.id,
            "person_state": initial_state.value,
            "compliant": event_data.compliant,
            "alert": {
                "id": str(alert.id),
                "severity": alert.severity.value,
                "message": alert.message
            } if alert else None
        }
    
    async def record_exit(self, case_id: UUID, staff_id: Optional[UUID] = None, 
                         person_track_id: Optional[int] = None,
                         timestamp: Optional[datetime] = None) -> Dict[str, Any]:
        """Record an exit event"""
        
        timestamp = timestamp or datetime.utcnow()
        
        exit_event = EntryExitEvent(
            case_id=case_id,
            staff_id=staff_id,
            person_track_id=person_track_id,
            event_type="EXIT",
            timestamp=timestamp,
            compliant=True  # Exit doesn't require compliance check
        )
        
        self.db.add(exit_event)
        await self.db.commit()
        
        # Clear person state from cache
        person_id = person_track_id or hash(str(staff_id))
        await RedisCache.delete(f"person_state:{case_id}:{person_id}")
        
        # Publish exit event
        await RedisPubSub.publish_case_event(str(case_id), "EXIT", {
            "event_id": str(exit_event.id),
            "staff_id": str(staff_id) if staff_id else None,
            "person_track_id": person_id,
            "timestamp": timestamp.isoformat()
        })
        
        return {
            "event_id": exit_event.id,
            "timestamp": timestamp.isoformat()
        }
    
    async def record_touch(self, event_data: TouchEventCreate) -> TouchEventWithStateResponse:
        """Record a touch event and update contamination state"""
        
        person_id = event_data.person_track_id or hash(str(event_data.staff_id))
        
        # Get current person state
        person_state_data = await RedisCache.get_person_state(str(event_data.case_id), person_id)
        
        if person_state_data:
            state_before = PersonState(person_state_data.get("state", "UNKNOWN"))
        else:
            state_before = PersonState.UNKNOWN
        
        # Determine new state based on touch
        state_after, alert = await self._process_touch_state_change(
            state_before, event_data.zone, event_data.surface, event_data.case_id
        )
        
        # Create touch event
        touch_event = TouchEvent(
            case_id=event_data.case_id,
            staff_id=event_data.staff_id,
            person_track_id=event_data.person_track_id,
            timestamp=event_data.timestamp,
            zone=event_data.zone,
            surface=event_data.surface,
            hand=event_data.hand,
            person_state_before=state_before.value,
            person_state_after=state_after.value,
            risk_level=self._get_zone_risk_level(event_data.zone),
            hand_position_x=event_data.position.get("x") if event_data.position else None,
            hand_position_y=event_data.position.get("y") if event_data.position else None,
            confidence=event_data.confidence
        )
        
        self.db.add(touch_event)
        
        # Create alert if needed
        alert_response = None
        if alert:
            alert_obj = Alert(
                case_id=event_data.case_id,
                staff_id=event_data.staff_id,
                touch_event_id=touch_event.id,
                alert_type=alert["type"],
                severity=alert["severity"],
                message=alert["message"],
                timestamp=event_data.timestamp
            )
            self.db.add(alert_obj)
            await self.db.flush()
            
            alert_response = {
                "id": str(alert_obj.id),
                "alert_type": alert["type"].value,
                "severity": alert["severity"].value,
                "message": alert["message"]
            }
            
            # Publish alert
            await RedisPubSub.publish_alert({
                "alert_id": str(alert_obj.id),
                "case_id": str(event_data.case_id),
                "alert_type": alert["type"].value,
                "severity": alert["severity"].value,
                "message": alert["message"],
                "timestamp": event_data.timestamp.isoformat()
            })
        
        await self.db.commit()
        
        # Update cached person state
        if person_state_data:
            person_state_data["state"] = state_after.value
            await RedisCache.set_person_state(str(event_data.case_id), person_id, person_state_data)
        
        # Publish touch event
        await RedisPubSub.publish_case_event(str(event_data.case_id), "TOUCH", {
            "event_id": str(touch_event.id),
            "staff_id": str(event_data.staff_id) if event_data.staff_id else None,
            "zone": event_data.zone.value,
            "surface": event_data.surface,
            "state_before": state_before.value,
            "state_after": state_after.value,
            "timestamp": event_data.timestamp.isoformat()
        })
        
        return TouchEventWithStateResponse(
            event_id=touch_event.id,
            state_change=StateChangeResponse(
                before=state_before,
                after=state_after
            ),
            alert_generated=alert_response
        )
    
    async def record_sanitize(self, case_id: UUID, staff_id: Optional[UUID] = None,
                              person_track_id: Optional[int] = None,
                              volume_ml: Optional[float] = None,
                              duration_sec: Optional[float] = None,
                              timestamp: Optional[datetime] = None) -> Dict[str, Any]:
        """Record a sanitization event"""
        
        timestamp = timestamp or datetime.utcnow()
        person_id = person_track_id or hash(str(staff_id))
        
        # Check if valid sanitization
        is_valid = True
        if volume_ml is not None and volume_ml < settings.SANITIZE_MIN_VOLUME_ML:
            is_valid = False
        if duration_sec is not None and duration_sec < settings.SANITIZE_MIN_DURATION_SEC:
            is_valid = False
        
        # Update person state
        person_state_data = await RedisCache.get_person_state(str(case_id), person_id)
        state_before = PersonState(person_state_data.get("state", "UNKNOWN")) if person_state_data else PersonState.UNKNOWN
        
        if is_valid:
            state_after = PersonState.CLEAN
        else:
            state_after = state_before  # State doesn't change if invalid sanitization
        
        # Update cache
        if person_state_data:
            person_state_data["state"] = state_after.value
            person_state_data["last_sanitize"] = timestamp.isoformat() if is_valid else person_state_data.get("last_sanitize")
            await RedisCache.set_person_state(str(case_id), person_id, person_state_data)
        
        # Create touch event for sanitizer zone
        touch_event = TouchEvent(
            case_id=case_id,
            staff_id=staff_id,
            person_track_id=person_track_id,
            timestamp=timestamp,
            zone=Zone.SANITIZER,
            surface="sanitizer_dispenser",
            person_state_before=state_before.value,
            person_state_after=state_after.value,
            risk_level=0
        )
        
        self.db.add(touch_event)
        await self.db.commit()
        
        # Publish event
        await RedisPubSub.publish_case_event(str(case_id), "SANITIZE", {
            "staff_id": str(staff_id) if staff_id else None,
            "person_track_id": person_id,
            "is_valid": is_valid,
            "volume_ml": volume_ml,
            "duration_sec": duration_sec,
            "state_before": state_before.value,
            "state_after": state_after.value,
            "timestamp": timestamp.isoformat()
        })
        
        return {
            "is_valid": is_valid,
            "state_before": state_before.value,
            "state_after": state_after.value,
            "volume_ml": volume_ml,
            "duration_sec": duration_sec
        }
    
    async def _process_touch_state_change(
        self, 
        current_state: PersonState, 
        zone: Zone, 
        surface: Optional[str],
        case_id: UUID
    ) -> tuple[PersonState, Optional[Dict]]:
        """Process state change based on touch event"""
        
        alert = None
        new_state = current_state
        
        # Contamination sources
        contamination_surfaces = {"phone", "face", "hair", "pocket", "floor", "shoes"}
        high_contamination_surfaces = {"phone", "face", "hair", "floor"}
        
        # Handle sanitizer zone (re-sanitization)
        if zone == Zone.SANITIZER:
            return PersonState.CLEAN, None
        
        # Handle touch based on current state
        if current_state == PersonState.CLEAN:
            # Check if touching contamination source
            if surface and surface.lower() in high_contamination_surfaces:
                new_state = PersonState.CONTAMINATED
                alert = {
                    "type": AlertType.CONTAMINATION,
                    "severity": AlertSeverity.HIGH,
                    "message": f"Contamination detected: touched {surface}"
                }
            elif surface and surface.lower() in contamination_surfaces:
                new_state = PersonState.POTENTIALLY_CONTAMINATED
                alert = {
                    "type": AlertType.CONTAMINATION,
                    "severity": AlertSeverity.MEDIUM,
                    "message": f"Potential contamination: touched {surface}"
                }
            elif zone == Zone.NON_STERILE:
                new_state = PersonState.POTENTIALLY_CONTAMINATED
        
        elif current_state == PersonState.POTENTIALLY_CONTAMINATED:
            # Escalate if touching critical zone
            if zone == Zone.CRITICAL:
                alert = {
                    "type": AlertType.CRITICAL_ZONE,
                    "severity": AlertSeverity.CRITICAL,
                    "message": "CRITICAL: Potentially contaminated hands in critical zone!"
                }
            elif zone == Zone.STERILE:
                alert = {
                    "type": AlertType.CONTAMINATION,
                    "severity": AlertSeverity.HIGH,
                    "message": "Potentially contaminated hands in sterile zone"
                }
            # Further contamination
            if surface and surface.lower() in high_contamination_surfaces:
                new_state = PersonState.CONTAMINATED
        
        elif current_state == PersonState.CONTAMINATED:
            # Any touch in sterile/critical zone is critical alert
            if zone == Zone.CRITICAL:
                alert = {
                    "type": AlertType.CRITICAL_ZONE,
                    "severity": AlertSeverity.CRITICAL,
                    "message": "CRITICAL ALERT: Contaminated hands reaching patient zone!"
                }
            elif zone == Zone.STERILE:
                alert = {
                    "type": AlertType.CONTAMINATION,
                    "severity": AlertSeverity.CRITICAL,
                    "message": "CRITICAL: Contaminated hands in sterile zone - resanitize immediately"
                }
        
        elif current_state == PersonState.DIRTY:
            # Person never sanitized - all touches in sterile/critical are alerts
            if zone in [Zone.CRITICAL, Zone.STERILE]:
                alert = {
                    "type": AlertType.MISSED_HYGIENE,
                    "severity": AlertSeverity.CRITICAL,
                    "message": "CRITICAL: Unsanitized hands in sterile/critical zone!"
                }
        
        return new_state, alert
    
    def _get_zone_risk_level(self, zone: Zone) -> int:
        """Get risk level for a zone"""
        risk_levels = {
            Zone.CRITICAL: 10,
            Zone.STERILE: 7,
            Zone.NON_STERILE: 3,
            Zone.SANITIZER: 0,
            Zone.DOOR: 1
        }
        return risk_levels.get(zone, 5)
