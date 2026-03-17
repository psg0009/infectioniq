"""
Frame Sampler — Training Data Collection
==========================================
Saves anonymized frames during live pipeline operation.
Designed to run silently alongside the main CV pipeline during pilots.

Collected frames are used for:
  - Level 1: Fine-tuning YOLOv8 on OR-specific data
  - Level 2: Training custom multi-task models
  - Level 3: Temporal action recognition datasets

Privacy:
  - Faces are blurred before saving
  - No patient-identifiable content (camera points at staff, not patient)
  - Metadata contains only track IDs and zone info, no PHI
"""

import os
import cv2
import json
import time
import logging
import numpy as np
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class FrameAnnotation:
    """Metadata saved alongside each sampled frame."""
    frame_number: int
    timestamp: str
    or_number: str
    persons: List[dict] = field(default_factory=list)
    # Each person: {track_id, bbox, state, hands_visible, zone, gesture_score}


@dataclass
class SamplerConfig:
    """Configuration for frame sampling behavior."""
    enabled: bool = True
    output_dir: str = "./training_data"
    sample_interval_sec: float = 1.0         # Save 1 frame per second
    blur_faces: bool = True                  # Privacy: blur face regions
    blur_kernel_size: int = 51               # Gaussian blur kernel
    save_annotations: bool = True            # Save JSON metadata alongside frames
    max_frames_per_session: int = 10000      # Stop after N frames to limit disk
    save_format: str = "jpg"                 # jpg (smaller) or png (lossless)
    jpeg_quality: int = 85                   # 0-100, balance quality vs size


class FrameSampler:
    """Collects anonymized training frames during live CV pipeline operation."""

    def __init__(self, config: SamplerConfig = None, or_number: str = "OR-1"):
        self.config = config or SamplerConfig()
        self.or_number = or_number

        self._last_sample_time = 0.0
        self._sample_count = 0
        self._session_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        # Create output directory structure
        self._session_dir = os.path.join(
            self.config.output_dir, self.or_number, self._session_id
        )
        self._frames_dir = os.path.join(self._session_dir, "frames")
        self._annotations_dir = os.path.join(self._session_dir, "annotations")

        if self.config.enabled:
            os.makedirs(self._frames_dir, exist_ok=True)
            os.makedirs(self._annotations_dir, exist_ok=True)

            # Write session metadata
            session_meta = {
                "session_id": self._session_id,
                "or_number": self.or_number,
                "started_at": datetime.utcnow().isoformat(),
                "config": asdict(self.config),
            }
            meta_path = os.path.join(self._session_dir, "session.json")
            with open(meta_path, "w") as f:
                json.dump(session_meta, f, indent=2)

            logger.info(
                f"Frame sampler initialized: {self._session_dir} "
                f"(every {self.config.sample_interval_sec}s)"
            )

    @property
    def sample_count(self) -> int:
        return self._sample_count

    @property
    def session_dir(self) -> str:
        return self._session_dir

    def should_sample(self) -> bool:
        """Check if enough time has passed to sample another frame."""
        if not self.config.enabled:
            return False
        if self._sample_count >= self.config.max_frames_per_session:
            return False
        now = time.time()
        if now - self._last_sample_time >= self.config.sample_interval_sec:
            return True
        return False

    def sample(
        self,
        frame: np.ndarray,
        frame_number: int,
        persons: list = None,
        state_machine=None,
        zone_detector=None,
        gesture_classifier=None,
    ) -> Optional[str]:
        """
        Save an anonymized frame + annotation.

        Args:
            frame: Raw BGR frame from camera
            frame_number: Current frame counter
            persons: List of DetectedPerson objects from person detector
            state_machine: ContaminationStateMachine for person states
            zone_detector: ZoneDetector for zone info
            gesture_classifier: GestureClassifier for gesture scores

        Returns:
            Path to saved frame, or None if not sampled
        """
        if not self.should_sample():
            return None

        self._last_sample_time = time.time()
        self._sample_count += 1

        # Make a copy to avoid modifying the display frame
        save_frame = frame.copy()

        # Privacy: blur face regions
        if self.config.blur_faces and persons:
            save_frame = self._blur_faces(save_frame, persons)

        # Save frame
        filename = f"{self._sample_count:06d}.{self.config.save_format}"
        frame_path = os.path.join(self._frames_dir, filename)

        if self.config.save_format == "jpg":
            cv2.imwrite(frame_path, save_frame,
                        [cv2.IMWRITE_JPEG_QUALITY, self.config.jpeg_quality])
        else:
            cv2.imwrite(frame_path, save_frame)

        # Save annotation
        if self.config.save_annotations:
            annotation = self._build_annotation(
                frame_number, persons, state_machine, zone_detector, gesture_classifier
            )
            ann_filename = f"{self._sample_count:06d}.json"
            ann_path = os.path.join(self._annotations_dir, ann_filename)
            with open(ann_path, "w") as f:
                json.dump(asdict(annotation), f, indent=2)

        if self._sample_count % 100 == 0:
            logger.info(f"Frame sampler: {self._sample_count} frames collected")

        return frame_path

    def _blur_faces(self, frame: np.ndarray, persons: list) -> np.ndarray:
        """Blur the upper portion of each detected person's bounding box (head/face region)."""
        h, w = frame.shape[:2]
        k = self.config.blur_kernel_size

        for person in persons:
            x1, y1, x2, y2 = person.bbox

            # Face region = top 30% of person bounding box
            face_bottom = y1 + int((y2 - y1) * 0.30)

            # Clamp to frame bounds
            fx1 = max(0, x1)
            fy1 = max(0, y1)
            fx2 = min(w, x2)
            fy2 = min(h, face_bottom)

            if fx2 > fx1 and fy2 > fy1:
                roi = frame[fy1:fy2, fx1:fx2]
                blurred = cv2.GaussianBlur(roi, (k, k), 0)
                frame[fy1:fy2, fx1:fx2] = blurred

        return frame

    def _build_annotation(
        self, frame_number, persons, state_machine, zone_detector, gesture_classifier
    ) -> FrameAnnotation:
        """Build annotation metadata for a sampled frame."""
        annotation = FrameAnnotation(
            frame_number=frame_number,
            timestamp=datetime.utcnow().isoformat(),
            or_number=self.or_number,
        )

        if not persons:
            return annotation

        for person in persons:
            person_data = {
                "track_id": person.track_id,
                "bbox": list(person.bbox),
                "confidence": round(person.confidence, 3),
            }

            # Add state info
            if state_machine:
                state = state_machine.get_state(person.track_id)
                person_data["state"] = state.value

            # Add gesture score
            if gesture_classifier:
                result = gesture_classifier.classify(person.track_id)
                if result:
                    person_data["gesture_score"] = round(result.score, 3)
                    person_data["is_sanitizing"] = result.is_sanitizing

            annotation.persons.append(person_data)

        return annotation

    def close(self):
        """Finalize the sampling session."""
        if not self.config.enabled:
            return

        # Write final session metadata
        meta_path = os.path.join(self._session_dir, "session.json")
        try:
            with open(meta_path, "r") as f:
                meta = json.load(f)
            meta["ended_at"] = datetime.utcnow().isoformat()
            meta["total_frames"] = self._sample_count
            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to update session metadata: {e}")

        logger.info(
            f"Frame sampler closed: {self._sample_count} frames saved to {self._session_dir}"
        )
