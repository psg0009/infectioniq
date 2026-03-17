"""Hand Tracking using MediaPipe Tasks API"""
import cv2
import numpy as np
from typing import List, Tuple, Optional
import logging
import os

from src.utils.types import HandLandmarks

logger = logging.getLogger(__name__)

MEDIAPIPE_AVAILABLE = False
USE_LEGACY_API = False

try:
    import mediapipe as mp
    # Check if using new tasks API or legacy solutions API
    if hasattr(mp, 'tasks'):
        MEDIAPIPE_AVAILABLE = True
        USE_LEGACY_API = False
    elif hasattr(mp, 'solutions'):
        MEDIAPIPE_AVAILABLE = True
        USE_LEGACY_API = True
except ImportError:
    pass


class HandTracker:
    """Tracks hands using MediaPipe"""

    def __init__(self, max_hands: int = 2, min_confidence: float = 0.5):
        self.max_hands = max_hands
        self.min_confidence = min_confidence
        self.use_mediapipe = False
        self.hands = None

        if not MEDIAPIPE_AVAILABLE:
            logger.warning("MediaPipe not available, hand tracking disabled")
            return

        if USE_LEGACY_API:
            self._init_legacy()
        else:
            self._init_tasks()

    def _init_legacy(self):
        """Initialize using legacy solutions API"""
        try:
            import mediapipe as mp
            self.mp_hands = mp.solutions.hands
            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=self.max_hands,
                min_detection_confidence=self.min_confidence,
                min_tracking_confidence=self.min_confidence
            )
            self.use_mediapipe = True
            self.is_legacy = True
            logger.info("Using MediaPipe legacy solutions API")
        except Exception as e:
            logger.error(f"Failed to init legacy MediaPipe: {e}")

    def _init_tasks(self):
        """Initialize using new tasks API"""
        try:
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            # Download model if not exists
            model_path = self._get_model_path()

            if model_path and os.path.exists(model_path):
                base_options = python.BaseOptions(model_asset_path=model_path)
                options = vision.HandLandmarkerOptions(
                    base_options=base_options,
                    running_mode=vision.RunningMode.IMAGE,
                    num_hands=self.max_hands,
                    min_hand_detection_confidence=self.min_confidence,
                    min_hand_presence_confidence=self.min_confidence,
                    min_tracking_confidence=self.min_confidence
                )
                self.hands = vision.HandLandmarker.create_from_options(options)
                self.use_mediapipe = True
                self.is_legacy = False
                logger.info("Using MediaPipe tasks API")
            else:
                logger.warning("MediaPipe hand model not found, hand tracking disabled")
                logger.info("Download from: https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task")
        except Exception as e:
            logger.error(f"Failed to init MediaPipe tasks: {e}")

    def _get_model_path(self) -> Optional[str]:
        """Get path to hand landmarker model"""
        # Check common locations
        possible_paths = [
            "hand_landmarker.task",
            "models/hand_landmarker.task",
            "../models/hand_landmarker.task",
            os.path.join(os.path.dirname(__file__), "hand_landmarker.task"),
            os.path.join(os.path.dirname(__file__), "..", "models", "hand_landmarker.task"),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        return None

    def track(self, frame: np.ndarray) -> List[HandLandmarks]:
        """Track hands in frame"""
        if not self.use_mediapipe or self.hands is None:
            return []

        if hasattr(self, 'is_legacy') and self.is_legacy:
            return self._track_legacy(frame)
        else:
            return self._track_tasks(frame)

    def _track_legacy(self, frame: np.ndarray) -> List[HandLandmarks]:
        """Track using legacy API"""
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_frame)

        hands = []
        if results.multi_hand_landmarks:
            for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
                handedness = "Right"
                confidence = 0.9

                if results.multi_handedness:
                    handedness = results.multi_handedness[i].classification[0].label
                    confidence = results.multi_handedness[i].classification[0].score

                landmarks = []
                h, w = frame.shape[:2]
                for lm in hand_landmarks.landmark:
                    landmarks.append((lm.x * w, lm.y * h, lm.z))

                hands.append(HandLandmarks(
                    landmarks=landmarks,
                    handedness=handedness,
                    confidence=confidence
                ))

        return hands

    def _track_tasks(self, frame: np.ndarray) -> List[HandLandmarks]:
        """Track using tasks API"""
        try:
            import mediapipe as mp

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            results = self.hands.detect(mp_image)

            hands = []
            if results.hand_landmarks:
                h, w = frame.shape[:2]

                for i, hand_landmarks in enumerate(results.hand_landmarks):
                    handedness = "Right"
                    confidence = 0.9

                    if results.handedness and i < len(results.handedness):
                        handedness = results.handedness[i][0].category_name
                        confidence = results.handedness[i][0].score

                    landmarks = []
                    for lm in hand_landmarks:
                        landmarks.append((lm.x * w, lm.y * h, lm.z))

                    hands.append(HandLandmarks(
                        landmarks=landmarks,
                        handedness=handedness,
                        confidence=confidence
                    ))

            return hands
        except Exception as e:
            logger.error(f"Hand tracking error: {e}")
            return []

    def close(self):
        """Clean up resources"""
        if self.hands is not None:
            if hasattr(self, 'is_legacy') and self.is_legacy:
                self.hands.close()
            else:
                # Tasks API handles cleanup automatically
                pass
