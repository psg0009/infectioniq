"""Contamination State Machine with state expiry"""
from typing import Dict, List, Optional, Tuple
import time
import logging

from src.utils.types import PersonState, Zone

logger = logging.getLogger(__name__)


class ContaminationStateMachine:
    """Tracks contamination state for each person with automatic state expiry.

    State expiry rules:
        - CLEAN expires after 300 seconds (5 min) and reverts to UNKNOWN,
          meaning the person must re-sanitize.
        - UNKNOWN expires after 600 seconds (10 min) and the person is removed
          from tracking entirely.
    """

    # Expiry configuration: state -> seconds until expiry
    # States not listed here never expire on their own.
    STATE_EXPIRY: Dict[PersonState, float] = {
        PersonState.CLEAN: 300.0,    # 5 minutes -> becomes UNKNOWN
        PersonState.UNKNOWN: 600.0,  # 10 minutes -> removed from tracking
    }

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

    def _check_expiry(self, person_id: int) -> None:
        """Check if the given person's state has expired and apply transitions.

        - CLEAN that has expired becomes UNKNOWN (needs re-sanitization).
        - UNKNOWN that has expired causes the person to be removed from tracking.
        """
        if person_id not in self.person_states:
            return

        current_state = self.person_states[person_id]
        timestamp = self.state_timestamps.get(person_id)

        if timestamp is None:
            return

        expiry_duration = self.STATE_EXPIRY.get(current_state)
        if expiry_duration is None:
            # This state does not expire
            return

        elapsed = time.time() - timestamp

        if elapsed < expiry_duration:
            # Not expired yet
            return

        if current_state == PersonState.CLEAN:
            # CLEAN expired -> transition to UNKNOWN
            logger.info(
                f"Person {person_id} CLEAN state expired after {elapsed:.1f}s, "
                f"reverting to UNKNOWN (needs re-sanitization)"
            )
            self.person_states[person_id] = PersonState.UNKNOWN
            self.state_timestamps[person_id] = time.time()
        elif current_state == PersonState.UNKNOWN:
            # UNKNOWN expired -> remove from tracking
            logger.info(
                f"Person {person_id} UNKNOWN state expired after {elapsed:.1f}s, "
                f"removing from tracking"
            )
            del self.person_states[person_id]
            del self.state_timestamps[person_id]

    def get_state(self, person_id: int) -> PersonState:
        """Get the current state of a person, checking for expiry first."""
        self._check_expiry(person_id)
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
                self.state_timestamps[person_id] = time.time()
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

    def cleanup_expired(self) -> List[int]:
        """Check all tracked persons for state expiry and apply transitions.

        This method is designed to be called once per frame from the main loop.

        Returns:
            A list of person_ids that were removed from tracking due to
            UNKNOWN state expiry.
        """
        removed_ids = []
        # Iterate over a snapshot of keys since _check_expiry may delete entries
        person_ids = list(self.person_states.keys())

        for person_id in person_ids:
            was_tracked = person_id in self.person_states
            self._check_expiry(person_id)
            if was_tracked and person_id not in self.person_states:
                removed_ids.append(person_id)

        if removed_ids:
            logger.info(f"cleanup_expired removed {len(removed_ids)} person(s): {removed_ids}")

        return removed_ids
