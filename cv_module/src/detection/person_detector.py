"""Person Detection using YOLOv8"""
import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple
import logging

from src.utils.math_utils import euclidean_distance
from config import PERSON_MAX_TRACK_DISTANCE_PX

logger = logging.getLogger(__name__)

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    logger.warning("ultralytics not installed, using fallback detection")


@dataclass
class DetectedPerson:
    """Detected person with bounding box and tracking ID"""
    track_id: int
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    confidence: float


class PersonDetector:
    """Detects people in frames using YOLOv8"""

    def __init__(self, model_path: str = "yolov8n.pt", confidence_threshold: float = 0.5):
        self.confidence_threshold = confidence_threshold
        self.track_id_counter = 0
        self.previous_detections: List[DetectedPerson] = []

        if YOLO_AVAILABLE:
            try:
                self.model = YOLO(model_path)
                self.use_yolo = True
                logger.info(f"Loaded YOLO model: {model_path}")
            except Exception as e:
                logger.error(f"Failed to load YOLO model: {e}")
                self.use_yolo = False
        else:
            self.use_yolo = False
            logger.warning("Using fallback person detection (no YOLO)")

    def detect(self, frame: np.ndarray) -> List[DetectedPerson]:
        """Detect people in frame"""
        if self.use_yolo:
            return self._detect_yolo(frame)
        else:
            return self._detect_fallback(frame)

    def _detect_yolo(self, frame: np.ndarray) -> List[DetectedPerson]:
        """Detect using YOLOv8"""
        results = self.model.track(frame, persist=True, classes=[0], verbose=False)  # class 0 = person

        persons = []
        if results and len(results) > 0:
            result = results[0]

            if result.boxes is not None:
                for box in result.boxes:
                    confidence = float(box.conf[0])

                    if confidence < self.confidence_threshold:
                        continue

                    # Get bounding box
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)

                    # Get track ID (or assign new one)
                    if box.id is not None:
                        track_id = int(box.id[0])
                    else:
                        track_id = self._assign_track_id((x1, y1, x2, y2))

                    persons.append(DetectedPerson(
                        track_id=track_id,
                        bbox=(x1, y1, x2, y2),
                        confidence=confidence
                    ))

        self.previous_detections = persons
        return persons

    def _detect_fallback(self, frame: np.ndarray) -> List[DetectedPerson]:
        """Fallback detection using OpenCV HOG detector"""
        hog = cv2.HOGDescriptor()
        hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

        # Resize for faster processing
        scale = 0.5
        small_frame = cv2.resize(frame, None, fx=scale, fy=scale)

        # Detect
        boxes, weights = hog.detectMultiScale(
            small_frame,
            winStride=(8, 8),
            padding=(4, 4),
            scale=1.05
        )

        persons = []
        for i, (x, y, w, h) in enumerate(boxes):
            # Scale back to original size
            x1 = int(x / scale)
            y1 = int(y / scale)
            x2 = int((x + w) / scale)
            y2 = int((y + h) / scale)

            confidence = float(weights[i]) if i < len(weights) else 0.5

            if confidence < self.confidence_threshold:
                continue

            track_id = self._assign_track_id((x1, y1, x2, y2))

            persons.append(DetectedPerson(
                track_id=track_id,
                bbox=(x1, y1, x2, y2),
                confidence=confidence
            ))

        self.previous_detections = persons
        return persons

    def _assign_track_id(self, bbox: Tuple[int, int, int, int]) -> int:
        """Simple tracking by matching with previous detections"""
        x1, y1, x2, y2 = bbox
        center = ((x1 + x2) // 2, (y1 + y2) // 2)

        # Try to match with previous detection
        min_dist = float('inf')
        matched_id = None

        for prev in self.previous_detections:
            px1, py1, px2, py2 = prev.bbox
            prev_center = ((px1 + px2) // 2, (py1 + py2) // 2)

            dist = euclidean_distance(center, prev_center)

            if dist < min_dist and dist < PERSON_MAX_TRACK_DISTANCE_PX:
                min_dist = dist
                matched_id = prev.track_id

        if matched_id is not None:
            return matched_id

        # Assign new ID
        self.track_id_counter += 1
        return self.track_id_counter
