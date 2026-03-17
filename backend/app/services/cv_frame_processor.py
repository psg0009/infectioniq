"""
CV Frame Processor - processes individual video frames through the CV pipeline.

Used by the WebSocket camera handler to run real-time detection on browser frames.
Lazily loads CV components on first use; gracefully degrades if dependencies missing.
"""

import sys
import os
import logging
import asyncio
import base64
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Add cv_module to Python path so we can import its components
_project_root = Path(__file__).resolve().parents[3]
_cv_path = str(_project_root / "cv_module")
if _cv_path not in sys.path:
    sys.path.insert(0, _cv_path)


class FrameProcessor:
    """Processes video frames through the CV pipeline components.

    Singleton-ish: one instance per WebSocket connection, but the heavy
    ML models (YOLO, MediaPipe) are loaded once and shared.
    """

    # Class-level shared models (loaded once)
    _person_detector = None
    _models_loaded = False
    _models_error: Optional[str] = None

    def __init__(self, case_id: Optional[str] = None, or_number: str = "OR-1"):
        self.case_id = case_id
        self.or_number = or_number
        self.frame_count = 0
        self.tracked_persons: Dict[int, dict] = {}

        # Per-instance components (lightweight)
        self.hand_tracker = None
        self.gesture_classifier = None
        self.zone_detector = None
        self.state_machine = None
        self._initialized = False

    @classmethod
    def _load_models(cls):
        """Load heavy ML models once (class-level)."""
        if cls._models_loaded:
            return cls._models_error is None
        cls._models_loaded = True
        try:
            from src.detection.person_detector import PersonDetector
            cls._person_detector = PersonDetector()
            logger.info("CV models loaded successfully")
            return True
        except Exception as e:
            cls._models_error = str(e)
            logger.error(f"Failed to load CV models: {e}")
            return False

    def initialize(self) -> bool:
        """Initialize per-instance pipeline components. Returns True on success."""
        if self._initialized:
            return self._models_error is None

        self._initialized = True
        try:
            # Load shared models
            if not self._load_models():
                return False

            from src.tracking.hand_tracker import HandTracker
            from src.classification.gesture_classifier import GestureClassifier
            from src.state.contamination_fsm import ContaminationStateMachine

            self.hand_tracker = HandTracker()
            self.gesture_classifier = GestureClassifier()
            self.state_machine = ContaminationStateMachine()
            logger.info("Frame processor initialized")
            return True

        except Exception as e:
            FrameProcessor._models_error = str(e)
            logger.error(f"Frame processor init failed: {e}")
            return False

    def process_frame(self, jpeg_bytes: bytes) -> Dict[str, Any]:
        """Process a single JPEG frame and return detection results."""
        import numpy as np
        import cv2

        if not self.initialize():
            return {
                "type": "error",
                "message": f"CV pipeline not available: {self._models_error}",
            }

        # Decode JPEG
        nparr = np.frombuffer(jpeg_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            return {"type": "error", "message": "Failed to decode frame"}

        h, w = frame.shape[:2]
        self.frame_count += 1

        # Initialize zone detector with actual frame resolution
        if self.zone_detector is None:
            from src.zones.zone_detector import ZoneDetector
            self.zone_detector = ZoneDetector(w, h)

        # Cleanup expired states
        removed_ids = self.state_machine.cleanup_expired()
        for pid in removed_ids:
            self.tracked_persons.pop(pid, None)

        # --- Stage 1: Person Detection ---
        persons = self._person_detector.detect(frame)

        # --- Stage 2+3+4: Hand tracking, gesture, zone for each person ---
        events: List[dict] = []
        person_results: List[dict] = []

        for person in persons:
            pid = person.track_id
            x1, y1, x2, y2 = person.bbox
            person_roi = frame[y1:y2, x1:x2]
            if person_roi.size == 0:
                continue

            # Hand tracking
            hands = self.hand_tracker.track(person_roi)
            hand_count = len(hands) if hands else 0

            # Transform hand coords to frame space
            if hands:
                for hand in hands:
                    hand.landmarks = [
                        (lm[0] * (x2 - x1) + x1, lm[1] * (y2 - y1) + y1, lm[2])
                        for lm in hand.landmarks
                    ]

            # Gesture classification
            is_sanitizing = False
            gesture_score = 0.0
            if hands:
                self.gesture_classifier.update(pid, hands)
                gesture_result = self.gesture_classifier.classify(pid)
                is_sanitizing = gesture_result.is_sanitizing
                gesture_score = gesture_result.score

            # New person entry
            if pid not in self.tracked_persons:
                self.state_machine.on_entry(pid)
                if is_sanitizing:
                    self.state_machine.on_sanitize(pid)
                self.tracked_persons[pid] = {
                    "entry_time": datetime.utcnow().isoformat(),
                    "sanitized": is_sanitizing,
                    "last_zone": None,
                }
                events.append({
                    "type": "ENTRY",
                    "person_track_id": pid,
                    "compliant": is_sanitizing,
                    "timestamp": datetime.utcnow().isoformat(),
                })
            else:
                if is_sanitizing:
                    self.tracked_persons[pid]["sanitized"] = True

            # Zone detection
            zone_name = None
            if hands and self.zone_detector:
                from src.utils.math_utils import get_palm_center
                for hand in hands:
                    palm = get_palm_center(hand.landmarks)
                    zone = self.zone_detector.get_zone_from_pixel(
                        (int(palm[0]), int(palm[1]))
                    )
                    zone_name = zone.name if hasattr(zone, 'name') else str(zone)

                    if is_sanitizing:
                        self.state_machine.on_sanitize(pid)
                    elif zone_name not in ("DOOR", "SANITIZER"):
                        last_zone = self.tracked_persons.get(pid, {}).get("last_zone")
                        if last_zone != zone_name:
                            self.state_machine.on_touch(pid, None, zone)
                            if pid in self.tracked_persons:
                                self.tracked_persons[pid]["last_zone"] = zone_name

            # Get contamination state
            state = self.state_machine.get_state(pid)
            state_val = state.value if hasattr(state, 'value') else str(state)

            person_results.append({
                "track_id": pid,
                "bbox": [int(x1), int(y1), int(x2), int(y2)],
                "confidence": round(float(person.confidence), 2),
                "hands_detected": hand_count,
                "is_sanitizing": is_sanitizing,
                "gesture_score": round(gesture_score, 3),
                "zone": zone_name,
                "state": state_val,
                "compliant": self.tracked_persons.get(pid, {}).get("sanitized", False),
            })

        return {
            "type": "detection",
            "frame": self.frame_count,
            "timestamp": datetime.utcnow().isoformat(),
            "persons_detected": len(person_results),
            "persons": person_results,
            "events": events,
        }

    async def process_frame_async(self, jpeg_bytes: bytes) -> Dict[str, Any]:
        """Async wrapper — runs CV processing in a thread pool."""
        return await asyncio.to_thread(self.process_frame, jpeg_bytes)
