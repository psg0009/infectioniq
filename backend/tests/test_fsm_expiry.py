"""Tests for contamination FSM state expiry logic"""

import pytest
import time
from unittest.mock import patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "cv_module"))

from src.state.contamination_fsm import ContaminationStateMachine
from src.utils.types import PersonState, Zone


# ---------------------------------------------------------------------------
# Basic state transitions (sanity checks)
# ---------------------------------------------------------------------------

class TestBasicTransitions:
    def test_initial_state_is_unknown(self):
        fsm = ContaminationStateMachine()
        assert fsm.get_state(99) == PersonState.UNKNOWN

    def test_entry_sets_unknown(self):
        fsm = ContaminationStateMachine()
        state = fsm.on_entry(1)
        assert state == PersonState.UNKNOWN

    def test_sanitize_sets_clean(self):
        fsm = ContaminationStateMachine()
        fsm.on_entry(1)
        state = fsm.on_sanitize(1)
        assert state == PersonState.CLEAN

    def test_exit_removes_person(self):
        fsm = ContaminationStateMachine()
        fsm.on_entry(1)
        fsm.on_exit(1)
        # After exit, person is no longer tracked → defaults to UNKNOWN
        assert fsm.get_state(1) == PersonState.UNKNOWN
        assert 1 not in fsm.person_states

    def test_touch_contaminated_surface_while_clean(self):
        fsm = ContaminationStateMachine()
        fsm.on_entry(1)
        fsm.on_sanitize(1)
        state, alert = fsm.on_touch(1, "phone", Zone.NON_STERILE)
        assert state == PersonState.CONTAMINATED
        assert alert is True

    def test_touch_sanitizer_zone_no_alert(self):
        fsm = ContaminationStateMachine()
        fsm.on_entry(1)
        state, alert = fsm.on_touch(1, None, Zone.SANITIZER)
        assert alert is False


# ---------------------------------------------------------------------------
# State expiry
# ---------------------------------------------------------------------------

class TestStateExpiry:
    def test_clean_not_expired_within_window(self):
        fsm = ContaminationStateMachine()
        fsm.on_entry(1)
        fsm.on_sanitize(1)
        # Immediately after sanitize, CLEAN should still be CLEAN
        assert fsm.get_state(1) == PersonState.CLEAN

    def test_clean_expires_to_unknown(self):
        """CLEAN state should expire to UNKNOWN after 300 seconds."""
        fsm = ContaminationStateMachine()
        fsm.on_entry(1)
        fsm.on_sanitize(1)

        # Fast-forward time past 300s
        fsm.state_timestamps[1] = time.time() - 301
        state = fsm.get_state(1)
        assert state == PersonState.UNKNOWN

    def test_unknown_expires_and_removes(self):
        """UNKNOWN state should expire after 600 seconds and remove from tracking."""
        fsm = ContaminationStateMachine()
        fsm.on_entry(1)
        assert fsm.get_state(1) == PersonState.UNKNOWN

        # Fast-forward time past 600s
        fsm.state_timestamps[1] = time.time() - 601
        state = fsm.get_state(1)
        # Person should be removed from tracking; get_state returns UNKNOWN
        # but person_states dict should NOT contain the person
        assert state == PersonState.UNKNOWN
        assert 1 not in fsm.person_states

    def test_contaminated_never_expires(self):
        """CONTAMINATED state should NOT expire on its own."""
        fsm = ContaminationStateMachine()
        fsm.on_entry(1)
        fsm.on_sanitize(1)
        fsm.on_touch(1, "phone", Zone.NON_STERILE)
        assert fsm.get_state(1) == PersonState.CONTAMINATED

        # Even far in the future, it should stay CONTAMINATED
        fsm.state_timestamps[1] = time.time() - 10000
        assert fsm.get_state(1) == PersonState.CONTAMINATED

    def test_potentially_contaminated_never_expires(self):
        """POTENTIALLY_CONTAMINATED state should NOT expire on its own."""
        fsm = ContaminationStateMachine()
        fsm.on_entry(1)
        fsm.on_sanitize(1)
        fsm.on_touch(1, "pocket", Zone.NON_STERILE)
        assert fsm.get_state(1) == PersonState.POTENTIALLY_CONTAMINATED

        fsm.state_timestamps[1] = time.time() - 10000
        assert fsm.get_state(1) == PersonState.POTENTIALLY_CONTAMINATED

    def test_clean_expiry_resets_timestamp(self):
        """When CLEAN expires to UNKNOWN, the timestamp should be updated."""
        fsm = ContaminationStateMachine()
        fsm.on_entry(1)
        fsm.on_sanitize(1)
        old_time = time.time() - 301
        fsm.state_timestamps[1] = old_time

        fsm.get_state(1)  # triggers expiry

        assert fsm.person_states[1] == PersonState.UNKNOWN
        # Timestamp should be updated (newer than old_time)
        assert fsm.state_timestamps[1] > old_time


# ---------------------------------------------------------------------------
# cleanup_expired
# ---------------------------------------------------------------------------

class TestCleanupExpired:
    def test_cleanup_removes_expired_unknown(self):
        fsm = ContaminationStateMachine()
        fsm.on_entry(1)
        fsm.on_entry(2)
        fsm.on_entry(3)

        # Only person 1 has expired UNKNOWN
        fsm.state_timestamps[1] = time.time() - 601
        # Person 2 is recent
        # Person 3 is CLEAN and not expired
        fsm.on_sanitize(3)

        removed = fsm.cleanup_expired()
        assert 1 in removed
        assert 2 not in removed
        assert 3 not in removed

    def test_cleanup_transitions_expired_clean(self):
        fsm = ContaminationStateMachine()
        fsm.on_entry(1)
        fsm.on_sanitize(1)
        fsm.state_timestamps[1] = time.time() - 301

        removed = fsm.cleanup_expired()
        # CLEAN expires to UNKNOWN, not removed
        assert 1 not in removed
        assert fsm.person_states[1] == PersonState.UNKNOWN

    def test_cleanup_no_expired_returns_empty(self):
        fsm = ContaminationStateMachine()
        fsm.on_entry(1)
        fsm.on_entry(2)

        removed = fsm.cleanup_expired()
        assert removed == []

    def test_cleanup_multiple_removals(self):
        fsm = ContaminationStateMachine()
        for pid in range(1, 6):
            fsm.on_entry(pid)
            fsm.state_timestamps[pid] = time.time() - 601

        removed = fsm.cleanup_expired()
        assert len(removed) == 5
        assert len(fsm.person_states) == 0

    def test_cleanup_chain_clean_to_unknown_to_removed(self):
        """CLEAN → UNKNOWN → removed across two cleanup cycles."""
        fsm = ContaminationStateMachine()
        fsm.on_entry(1)
        fsm.on_sanitize(1)

        # First cleanup: CLEAN expired → UNKNOWN
        fsm.state_timestamps[1] = time.time() - 301
        removed = fsm.cleanup_expired()
        assert removed == []
        assert fsm.person_states[1] == PersonState.UNKNOWN

        # Second cleanup: UNKNOWN expired → removed
        fsm.state_timestamps[1] = time.time() - 601
        removed = fsm.cleanup_expired()
        assert 1 in removed
        assert 1 not in fsm.person_states


# ---------------------------------------------------------------------------
# Touch alerts in critical/sterile zones
# ---------------------------------------------------------------------------

class TestTouchAlerts:
    def test_contaminated_in_critical_zone_alerts(self):
        fsm = ContaminationStateMachine()
        fsm.on_entry(1)
        fsm.on_sanitize(1)
        fsm.on_touch(1, "phone", Zone.NON_STERILE)  # Now CONTAMINATED
        state, alert = fsm.on_touch(1, None, Zone.CRITICAL)
        assert alert is True

    def test_contaminated_in_sterile_zone_alerts(self):
        fsm = ContaminationStateMachine()
        fsm.on_entry(1)
        fsm.on_sanitize(1)
        fsm.on_touch(1, "phone", Zone.NON_STERILE)  # Now CONTAMINATED
        state, alert = fsm.on_touch(1, None, Zone.STERILE)
        assert alert is True

    def test_clean_in_critical_zone_no_alert(self):
        fsm = ContaminationStateMachine()
        fsm.on_entry(1)
        fsm.on_sanitize(1)
        state, alert = fsm.on_touch(1, None, Zone.CRITICAL)
        assert alert is False
