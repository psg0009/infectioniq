"""
InfectionIQ Computer Vision Module
Main entry point for the CV pipeline
"""

import cv2
import asyncio
import argparse
import logging
from datetime import datetime
import httpx
import json

from src.detection.person_detector import PersonDetector
from src.tracking.hand_tracker import HandTracker
from src.classification.gesture_classifier import GestureClassifier
from src.zones.zone_detector import ZoneDetector
from src.state.contamination_fsm import ContaminationStateMachine
from src.events.event_publisher import EventPublisher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CVPipeline:
    """Main Computer Vision Pipeline"""
    
    def __init__(
        self,
        camera_source: int = 0,
        backend_url: str = "http://localhost:8000",
        case_id: str = None,
        or_number: str = "OR-1"
    ):
        self.camera_source = camera_source
        self.backend_url = backend_url
        self.case_id = case_id
        self.or_number = or_number
        
        # Initialize components
        logger.info("Initializing CV Pipeline components...")
        
        self.person_detector = PersonDetector()
        self.hand_tracker = HandTracker()
        self.gesture_classifier = GestureClassifier()
        self.zone_detector = None  # Initialized after camera resolution known
        self.state_machine = ContaminationStateMachine()
        self.event_publisher = EventPublisher(backend_url)
        
        # State tracking
        self.tracked_persons = {}  # person_id -> PersonState
        self.frame_count = 0
        
        logger.info("CV Pipeline initialized")
    
    def run(self):
        """Run the CV pipeline"""
        
        logger.info(f"Opening camera source: {self.camera_source}")
        cap = cv2.VideoCapture(self.camera_source)
        
        if not cap.isOpened():
            logger.error("Failed to open camera")
            return
        
        # Get camera properties
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        logger.info(f"Camera: {width}x{height} @ {fps} FPS")
        
        # Initialize zone detector with camera resolution
        self.zone_detector = ZoneDetector(width, height)
        
        logger.info("Starting CV pipeline loop...")
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    logger.warning("Failed to read frame")
                    continue
                
                self.frame_count += 1
                
                # Process frame
                processed_frame, events = self.process_frame(frame)
                
                # Publish events
                for event in events:
                    asyncio.run(self.event_publisher.publish(event))
                
                # Display frame (for debugging)
                cv2.imshow("InfectionIQ CV Pipeline", processed_frame)
                
                # Check for quit
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        
        finally:
            cap.release()
            cv2.destroyAllWindows()
            logger.info("CV Pipeline stopped")
    
    def process_frame(self, frame):
        """Process a single frame through the pipeline"""
        
        events = []
        
        # Stage 1: Person Detection
        persons = self.person_detector.detect(frame)
        
        # Stage 2: For each person, track hands
        for person in persons:
            person_id = person.track_id
            
            # Extract person ROI
            x1, y1, x2, y2 = person.bbox
            person_roi = frame[y1:y2, x1:x2]
            
            if person_roi.size == 0:
                continue
            
            # Stage 3: Hand tracking
            hands = self.hand_tracker.track(person_roi)
            
            if not hands:
                continue
            
            # Transform hand coordinates to frame coordinates
            for hand in hands:
                hand.landmarks = [
                    (lm[0] * (x2 - x1) + x1, lm[1] * (y2 - y1) + y1, lm[2])
                    for lm in hand.landmarks
                ]
            
            # Stage 4: Gesture classification
            self.gesture_classifier.update(person_id, hands)
            is_sanitizing, confidence = self.gesture_classifier.is_sanitizing(person_id)
            
            # Stage 5: Zone detection
            for hand in hands:
                palm_center = self._get_palm_center(hand.landmarks)
                zone = self.zone_detector.get_zone_from_pixel(
                    (int(palm_center[0]), int(palm_center[1]))
                )
                
                # Check for entry/exit
                if zone.name == "DOOR":
                    if person_id not in self.tracked_persons:
                        # New person entering
                        event = self._handle_entry(person_id, is_sanitizing)
                        if event:
                            events.append(event)
                
                # Stage 6: State machine updates
                if is_sanitizing:
                    event = self._handle_sanitize(person_id)
                    if event:
                        events.append(event)
                elif zone.name not in ["DOOR", "SANITIZER"]:
                    event = self._handle_touch(person_id, zone, hand)
                    if event:
                        events.append(event)
            
            # Update tracking
            if person_id not in self.tracked_persons:
                self.tracked_persons[person_id] = {
                    "state": "UNKNOWN",
                    "entry_time": datetime.utcnow(),
                    "hands": hands
                }
            else:
                self.tracked_persons[person_id]["hands"] = hands
        
        # Draw visualizations
        processed_frame = self._draw_visualizations(frame, persons)
        
        return processed_frame, events
    
    def _get_palm_center(self, landmarks):
        """Calculate palm center from landmarks"""
        palm_indices = [0, 5, 9, 13, 17]
        palm_points = [landmarks[i] for i in palm_indices if i < len(landmarks)]
        
        if not palm_points:
            return (0, 0)
        
        x = sum(p[0] for p in palm_points) / len(palm_points)
        y = sum(p[1] for p in palm_points) / len(palm_points)
        return (x, y)
    
    def _handle_entry(self, person_id: int, is_sanitizing: bool):
        """Handle person entry event"""
        
        compliant = is_sanitizing
        
        self.state_machine.on_entry(person_id)
        if is_sanitizing:
            self.state_machine.on_sanitize(person_id)
        
        return {
            "type": "ENTRY",
            "data": {
                "case_id": self.case_id,
                "person_track_id": person_id,
                "timestamp": datetime.utcnow().isoformat(),
                "compliant": compliant,
                "sanitize_method": "SANITIZER" if compliant else "NONE"
            }
        }
    
    def _handle_sanitize(self, person_id: int):
        """Handle sanitization event"""
        
        old_state = self.state_machine.get_state(person_id)
        new_state = self.state_machine.on_sanitize(person_id)
        
        return {
            "type": "SANITIZE",
            "data": {
                "case_id": self.case_id,
                "person_track_id": person_id,
                "timestamp": datetime.utcnow().isoformat(),
                "state_before": old_state.value,
                "state_after": new_state.value
            }
        }
    
    def _handle_touch(self, person_id: int, zone, hand):
        """Handle touch event"""
        
        current_state = self.state_machine.get_state(person_id)
        new_state, alert = self.state_machine.on_touch(person_id, None, zone)
        
        event = {
            "type": "TOUCH",
            "data": {
                "case_id": self.case_id,
                "person_track_id": person_id,
                "timestamp": datetime.utcnow().isoformat(),
                "zone": zone.value,
                "hand": hand.handedness,
                "state_before": current_state.value,
                "state_after": new_state.value
            }
        }
        
        if alert:
            event["alert"] = {
                "type": "CONTAMINATION",
                "severity": "HIGH" if zone.value == "CRITICAL" else "MEDIUM",
                "message": f"Contamination detected in {zone.value} zone"
            }
        
        return event
    
    def _draw_visualizations(self, frame, persons):
        """Draw visualization overlays"""
        
        # Draw zones
        if self.zone_detector:
            frame = self.zone_detector.draw_zones(frame)
        
        # Draw person boxes and states
        for person in persons:
            x1, y1, x2, y2 = person.bbox
            
            # Get state color
            state = self.state_machine.get_state(person.track_id)
            color = self._get_state_color(state)
            
            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # Draw label
            label = f"ID:{person.track_id} [{state.value}]"
            cv2.putText(frame, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
            # Draw hands if tracked
            if person.track_id in self.tracked_persons:
                hands = self.tracked_persons[person.track_id].get("hands", [])
                for hand in hands:
                    self._draw_hand_landmarks(frame, hand.landmarks, color)
        
        # Draw frame info
        cv2.putText(frame, f"Frame: {self.frame_count}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        return frame
    
    def _get_state_color(self, state):
        """Get color for person state"""
        colors = {
            "UNKNOWN": (128, 128, 128),  # Gray
            "CLEAN": (0, 255, 0),         # Green
            "POTENTIALLY_CONTAMINATED": (0, 255, 255),  # Yellow
            "CONTAMINATED": (0, 128, 255),  # Orange
            "DIRTY": (0, 0, 255)           # Red
        }
        return colors.get(state.value, (255, 255, 255))
    
    def _draw_hand_landmarks(self, frame, landmarks, color):
        """Draw hand landmarks on frame"""
        for i, lm in enumerate(landmarks):
            x, y = int(lm[0]), int(lm[1])
            cv2.circle(frame, (x, y), 3, color, -1)


def main():
    parser = argparse.ArgumentParser(description="InfectionIQ CV Pipeline")
    parser.add_argument("--camera", type=int, default=0, help="Camera source")
    parser.add_argument("--backend", type=str, default="http://localhost:8000", help="Backend URL")
    parser.add_argument("--case-id", type=str, help="Active case ID")
    parser.add_argument("--or", type=str, default="OR-1", dest="or_number", help="OR number")
    
    args = parser.parse_args()
    
    pipeline = CVPipeline(
        camera_source=args.camera,
        backend_url=args.backend,
        case_id=args.case_id,
        or_number=args.or_number
    )
    
    pipeline.run()


if __name__ == "__main__":
    main()
