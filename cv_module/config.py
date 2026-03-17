"""CV Module Configuration - single source of truth for all thresholds"""

from dataclasses import dataclass, field

# Person detection
PERSON_CONFIDENCE_THRESHOLD = 0.5
PERSON_MAX_TRACK_DISTANCE_PX = 100

# Hand tracking
HAND_MAX_HANDS = 2
HAND_MIN_CONFIDENCE = 0.5

# Gesture classification
GESTURE_WINDOW_SIZE = 30
PALM_DISTANCE_THRESHOLD = 0.15
MOTION_THRESHOLD = 0.02
OSCILLATION_THRESHOLD = 4
SANITIZE_SCORE_THRESHOLD = 0.7


@dataclass
class GestureConfig:
    """Configurable gesture classification thresholds and weights."""
    # Sliding window size (frames)
    window_size: int = GESTURE_WINDOW_SIZE
    # Palm distance threshold (normalized coords) — hands closer than this score positive
    palm_distance_threshold: float = PALM_DISTANCE_THRESHOLD
    # Palm distance variance threshold — variance above this scores positive
    palm_variance_threshold: float = 0.001
    # Motion threshold (normalized coords) — avg motion above this scores positive
    motion_threshold: float = MOTION_THRESHOLD
    # Oscillation threshold — direction changes >= this scores positive
    oscillation_threshold: int = OSCILLATION_THRESHOLD
    # Overall score threshold to classify as sanitizing
    score_threshold: float = SANITIZE_SCORE_THRESHOLD
    # Minimum consecutive seconds above score threshold to confirm sanitization
    min_duration_sec: float = 3.0
    # Minimum fraction of frames with two hands visible
    two_hands_ratio: float = 0.6
    # Score weights for each feature (must sum to 1.0)
    weight_palm_close: float = 0.3
    weight_palm_variance: float = 0.2
    weight_motion: float = 0.2
    weight_oscillation: float = 0.3

# Zone defaults (normalized 0-1 coordinates)
DEFAULT_ZONES = {
    "DOOR": [[0.4, 0.85], [0.6, 0.85], [0.6, 1.0], [0.4, 1.0]],
    "SANITIZER": [[0.7, 0.8], [0.9, 0.8], [0.9, 1.0], [0.7, 1.0]],
    "NON_STERILE": [[0.0, 0.6], [1.0, 0.6], [1.0, 1.0], [0.0, 1.0]],
    "STERILE": [[0.1, 0.15], [0.9, 0.15], [0.9, 0.6], [0.1, 0.6]],
    "CRITICAL": [[0.25, 0.2], [0.75, 0.2], [0.75, 0.5], [0.25, 0.5]]
}

ZONE_RISK_LEVELS = {
    "DOOR": 1,
    "SANITIZER": 0,
    "NON_STERILE": 3,
    "STERILE": 7,
    "CRITICAL": 10
}

# Video playback
VIDEO_WAIT_TIME_MS = 33
CAMERA_WAIT_TIME_MS = 1

# Visualization colors (BGR for OpenCV)
STATE_COLORS = {
    "UNKNOWN": (128, 128, 128),
    "CLEAN": (0, 255, 0),
    "POTENTIALLY_CONTAMINATED": (0, 255, 255),
    "CONTAMINATED": (0, 128, 255),
    "DIRTY": (0, 0, 255)
}
