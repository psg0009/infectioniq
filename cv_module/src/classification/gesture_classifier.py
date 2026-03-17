"""Gesture Classification for Sanitizing Detection"""
import numpy as np
import time
from collections import deque
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
import logging

from src.utils.types import HandLandmarks
from src.utils.math_utils import get_palm_center, euclidean_distance
from config import GestureConfig

logger = logging.getLogger(__name__)


@dataclass
class GestureResult:
    """Detailed result from gesture classification."""
    is_sanitizing: bool
    score: float
    palm_distance: float = 0.0
    palm_close_score: float = 0.0
    variance_score: float = 0.0
    motion_score: float = 0.0
    oscillation_score: float = 0.0
    oscillation_count: int = 0
    duration_sec: float = 0.0


class GestureClassifier:
    """Classifies hand gestures, specifically sanitizing motion"""

    def __init__(self, config: Optional[GestureConfig] = None):
        self.config = config or GestureConfig()
        self.landmark_history: Dict[int, deque] = {}
        # Duration tracking: person_id -> timestamp when score first exceeded threshold
        self._streak_start: Dict[int, float] = {}

    def update(self, person_id: int, hands: List[HandLandmarks]):
        """Update landmark history for a person"""
        if person_id not in self.landmark_history:
            self.landmark_history[person_id] = deque(maxlen=self.config.window_size)
        self.landmark_history[person_id].append(hands)

    def classify(self, person_id: int) -> GestureResult:
        """Classify gesture for a person with full feature breakdown."""
        cfg = self.config

        if person_id not in self.landmark_history:
            self._reset_streak(person_id)
            return GestureResult(is_sanitizing=False, score=0.0)

        history = list(self.landmark_history[person_id])
        if len(history) < cfg.window_size // 2:
            self._reset_streak(person_id)
            return GestureResult(is_sanitizing=False, score=0.0)

        two_hands_frames = sum(1 for frame in history if len(frame) >= 2)
        if two_hands_frames < len(history) * cfg.two_hands_ratio:
            self._reset_streak(person_id)
            return GestureResult(is_sanitizing=False, score=0.0)

        # Compute features
        palm_distances = []
        motions = []
        prev_centers = None

        for frame in history:
            if len(frame) >= 2:
                left_hand = next((h for h in frame if h.handedness == "Left"), None)
                right_hand = next((h for h in frame if h.handedness == "Right"), None)

                if left_hand and right_hand:
                    left_palm = get_palm_center(left_hand.landmarks)
                    right_palm = get_palm_center(right_hand.landmarks)
                    palm_distances.append(euclidean_distance(left_palm, right_palm))

                    if prev_centers:
                        motion = euclidean_distance(left_palm, prev_centers[0])
                        motion += euclidean_distance(right_palm, prev_centers[1])
                        motions.append(motion / 2)
                    prev_centers = (left_palm, right_palm)

        if not palm_distances or not motions:
            self._reset_streak(person_id)
            return GestureResult(is_sanitizing=False, score=0.0)

        avg_palm_distance = float(np.mean(palm_distances))
        palm_distance_var = float(np.var(palm_distances))
        avg_motion = float(np.mean(motions))

        direction_changes = 0
        for i in range(2, len(motions)):
            if (motions[i] - motions[i - 1]) * (motions[i - 1] - motions[i - 2]) < 0:
                direction_changes += 1

        # Score each feature
        palm_close_score = cfg.weight_palm_close if avg_palm_distance < cfg.palm_distance_threshold else 0.0
        variance_score = cfg.weight_palm_variance if palm_distance_var > cfg.palm_variance_threshold else 0.0
        motion_s = cfg.weight_motion if avg_motion > cfg.motion_threshold else 0.0
        oscillation_score = cfg.weight_oscillation if direction_changes >= cfg.oscillation_threshold else 0.0

        score = palm_close_score + variance_score + motion_s + oscillation_score

        # Duration tracking
        now = time.time()
        if score >= cfg.score_threshold:
            if person_id not in self._streak_start:
                self._streak_start[person_id] = now
            duration = now - self._streak_start[person_id]
        else:
            self._reset_streak(person_id)
            duration = 0.0

        is_sanitizing = score >= cfg.score_threshold and duration >= cfg.min_duration_sec

        return GestureResult(
            is_sanitizing=is_sanitizing,
            score=score,
            palm_distance=avg_palm_distance,
            palm_close_score=palm_close_score,
            variance_score=variance_score,
            motion_score=motion_s,
            oscillation_score=oscillation_score,
            oscillation_count=direction_changes,
            duration_sec=duration,
        )

    def is_sanitizing(self, person_id: int) -> Tuple[bool, float]:
        """Backward-compatible wrapper around classify()."""
        result = self.classify(person_id)
        return result.is_sanitizing, result.score

    def _reset_streak(self, person_id: int):
        """Reset the duration streak for a person."""
        self._streak_start.pop(person_id, None)
