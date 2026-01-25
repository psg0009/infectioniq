"""Contamination State Machine"""
from enum import Enum
from typing import Dict, Optional, Tuple
import time

class PersonState(Enum):
    UNKNOWN = "UNKNOWN"
    CLEAN = "CLEAN"
    POTENTIALLY_CONTAMINATED = "POTENTIALLY_CONTAMINATED"
    CONTAMINATED = "CONTAMINATED"
    DIRTY = "DIRTY"

class Zone(Enum):
    DOOR = "DOOR"
    SANITIZER = "SANITIZER"
    NON_STERILE = "NON_STERILE"
    STERILE = "STERILE"
    CRITICAL = "CRITICAL"

class ContaminationStateMachine:
    """Tracks contamination state for each person"""
    
    def __init__(self):
        self.person_states: Dict[int, PersonState] = {}
        self.state_timestamps: Dict[int, float] = {}
        self.contamination_surfaces = {
            "phone": PersonState.CONTAMINATED,
            "face": PersonState.CONTAMINATED,
            "hair": PersonState.CONTAMINATED,
            "pocket": PersonState.POTENTIALLY_CONTAMINATED,
            "non_sterile_surface": PersonState.POTENTIALLY_CONTAMINATED
        }
    
    def get_state(self, person_id: int) -> PersonState:
        return self.person_states.get(person_id, PersonState.UNKNOWN)
    
    def on_entry(self, person_id: int) -> PersonState:
        self.person_states[person_id] = PersonState.UNKNOWN
        self.state_timestamps[person_id] = time.time()
        return PersonState.UNKNOWN
    
    def on_sanitize(self, person_id: int) -> PersonState:
        self.person_states[person_id] = PersonState.CLEAN
        self.state_timestamps[person_id] = time.time()
        return PersonState.CLEAN
    
    def on_touch(self, person_id: int, surface: Optional[str], zone: Zone) -> Tuple[PersonState, bool]:
        current_state = self.get_state(person_id)
        alert = False
        
        if zone == Zone.SANITIZER:
            return current_state, False
        
        if surface and surface in self.contamination_surfaces:
            if current_state == PersonState.CLEAN:
                new_state = self.contamination_surfaces[surface]
                self.person_states[person_id] = new_state
                return new_state, True
        
        if current_state in [PersonState.CONTAMINATED, PersonState.POTENTIALLY_CONTAMINATED]:
            if zone in [Zone.CRITICAL, Zone.STERILE]:
                return current_state, True
        
        if current_state == PersonState.DIRTY and zone in [Zone.CRITICAL, Zone.STERILE]:
            return current_state, True
        
        return current_state, alert
    
    def on_exit(self, person_id: int):
        if person_id in self.person_states:
            del self.person_states[person_id]
        if person_id in self.state_timestamps:
            del self.state_timestamps[person_id]
