"""Gesture Classification for Sanitizing Detection"""
import numpy as np
from collections import deque
from typing import List, Tuple, Dict
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class HandLandmarks:
    landmarks: List[Tuple[float, float, float]]
    handedness: str
    confidence: float

class GestureClassifier:
    """Classifies hand gestures, specifically sanitizing motion"""
    
    def __init__(self, window_size: int = 30):
        self.window_size = window_size
        self.landmark_history: Dict[int, deque] = {}
        self.PALM_DISTANCE_THRESHOLD = 0.15
        self.MOTION_THRESHOLD = 0.02
        self.OSCILLATION_THRESHOLD = 4
    
    def update(self, person_id: int, hands: List[HandLandmarks]):
        """Update landmark history for a person"""
        if person_id not in self.landmark_history:
            self.landmark_history[person_id] = deque(maxlen=self.window_size)
        self.landmark_history[person_id].append(hands)
    
    def _get_palm_center(self, landmarks: List[Tuple[float, float, float]]) -> Tuple[float, float]:
        palm_indices = [0, 5, 9, 13, 17]
        palm_points = [landmarks[i] for i in palm_indices if i < len(landmarks)]
        if not palm_points:
            return (0, 0)
        x = sum(p[0] for p in palm_points) / len(palm_points)
        y = sum(p[1] for p in palm_points) / len(palm_points)
        return (x, y)
    
    def _calculate_distance(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        return np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
    
    def is_sanitizing(self, person_id: int) -> Tuple[bool, float]:
        """Detect if person is performing sanitizing gesture"""
        if person_id not in self.landmark_history:
            return False, 0.0
        
        history = list(self.landmark_history[person_id])
        if len(history) < self.window_size // 2:
            return False, 0.0
        
        two_hands_frames = sum(1 for frame in history if len(frame) >= 2)
        if two_hands_frames < len(history) * 0.6:
            return False, 0.0
        
        palm_distances = []
        motions = []
        prev_centers = None
        
        for frame in history:
            if len(frame) >= 2:
                left_hand = next((h for h in frame if h.handedness == "Left"), None)
                right_hand = next((h for h in frame if h.handedness == "Right"), None)
                
                if left_hand and right_hand:
                    left_palm = self._get_palm_center(left_hand.landmarks)
                    right_palm = self._get_palm_center(right_hand.landmarks)
                    palm_distances.append(self._calculate_distance(left_palm, right_palm))
                    
                    if prev_centers:
                        motion = self._calculate_distance(left_palm, prev_centers[0])
                        motion += self._calculate_distance(right_palm, prev_centers[1])
                        motions.append(motion / 2)
                    prev_centers = (left_palm, right_palm)
        
        if not palm_distances or not motions:
            return False, 0.0
        
        avg_palm_distance = np.mean(palm_distances)
        palm_distance_var = np.var(palm_distances)
        avg_motion = np.mean(motions)
        
        direction_changes = 0
        for i in range(2, len(motions)):
            if (motions[i] - motions[i-1]) * (motions[i-1] - motions[i-2]) < 0:
                direction_changes += 1
        
        score = 0.0
        if avg_palm_distance < self.PALM_DISTANCE_THRESHOLD:
            score += 0.3
        if palm_distance_var > 0.001:
            score += 0.2
        if avg_motion > self.MOTION_THRESHOLD:
            score += 0.2
        if direction_changes >= self.OSCILLATION_THRESHOLD:
            score += 0.3
        
        return score >= 0.7, score
