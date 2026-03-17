"""
InfectionIQ Computer Vision Module
Main entry point for the CV pipeline
"""

import cv2
import asyncio
import argparse
import logging
import os
import time
from datetime import datetime
import httpx
import json

from src.detection.person_detector import PersonDetector
from src.tracking.hand_tracker import HandTracker
from src.classification.gesture_classifier import GestureClassifier, GestureResult
from src.zones.zone_detector import ZoneDetector
from src.state.contamination_fsm import ContaminationStateMachine
from src.events.event_publisher import EventPublisher
from src.utils.math_utils import get_palm_center
from src.utils.frame_sampler import FrameSampler, SamplerConfig
from config import STATE_COLORS, VIDEO_WAIT_TIME_MS, CAMERA_WAIT_TIME_MS, GestureConfig

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
        video_path: str = None,
        backend_url: str = None,
        case_id: str = None,
        or_number: str = "OR-1",
        loop_video: bool = True,
        gesture_config: GestureConfig = None,
        sample_frames: bool = False,
        sample_dir: str = "./training_data",
        headless: bool = False,
    ):
        self.camera_source = camera_source
        self.video_path = video_path
        self.backend_url = backend_url or os.environ.get("INFECTIONIQ_BACKEND_URL", "http://localhost:8000")
        self.case_id = case_id
        self.or_number = or_number
        self.loop_video = loop_video
        self.gesture_config = gesture_config or GestureConfig()
        self.sample_frames = sample_frames
        self.headless = headless or os.environ.get("INFECTIONIQ_HEADLESS") == "1"

        # Camera / heartbeat identifiers
        self.camera_id = f"cam-{or_number}"
        self._last_heartbeat = 0.0
        self._heartbeat_interval = 30  # seconds

        # Backend zone config (fetched at startup if available)
        self._backend_zones = None

        # Initialize components
        logger.info("Initializing CV Pipeline components...")

        self.person_detector = PersonDetector()
        self.hand_tracker = HandTracker()
        self.gesture_classifier = GestureClassifier(config=self.gesture_config)
        self.zone_detector = None  # Initialized after camera resolution known
        self.state_machine = ContaminationStateMachine()
        self.event_publisher = EventPublisher(backend_url)

        # Frame sampler for training data collection
        self.frame_sampler = None
        if self.sample_frames:
            sampler_config = SamplerConfig(enabled=True, output_dir=sample_dir)
            self.frame_sampler = FrameSampler(config=sampler_config, or_number=or_number)
            logger.info(f"Frame sampling enabled → {self.frame_sampler.session_dir}")

        # State tracking
        self.tracked_persons = {}  # person_id -> PersonState
        self.frame_count = 0
        self._last_persons = []  # Last detected persons (for frame sampler)

        # Try to fetch config from backend (non-blocking)
        try:
            asyncio.run(self._fetch_backend_config())
        except Exception as e:
            logger.warning(f"Could not fetch backend config at startup: {e}, using defaults")

        logger.info("CV Pipeline initialized")

    async def _fetch_backend_config(self):
        """Fetch zone config from backend at startup."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.backend_url}/api/v1/cameras/{self.camera_id}/config"
                )
                if resp.status_code == 200:
                    config = resp.json()
                    if "zones" in config:
                        logger.info(
                            f"Loaded zone config from backend: {len(config['zones'])} zones"
                        )
                        # Store for later use when zone_detector is initialized
                        self._backend_zones = config["zones"]
                    if "heartbeat_interval" in config:
                        self._heartbeat_interval = int(config["heartbeat_interval"])
                        logger.info(f"Heartbeat interval set to {self._heartbeat_interval}s from backend config")
                    if "gesture_config" in config:
                        gc = config["gesture_config"]
                        self.gesture_config = GestureConfig(
                            palm_distance_threshold=gc.get("palm_distance_threshold", self.gesture_config.palm_distance_threshold),
                            palm_variance_threshold=gc.get("palm_variance_threshold", self.gesture_config.palm_variance_threshold),
                            motion_threshold=gc.get("motion_threshold", self.gesture_config.motion_threshold),
                            oscillation_threshold=gc.get("oscillation_threshold", self.gesture_config.oscillation_threshold),
                            score_threshold=gc.get("score_threshold", self.gesture_config.score_threshold),
                            min_duration_sec=gc.get("min_duration_sec", self.gesture_config.min_duration_sec),
                            weight_palm_close=gc.get("weight_palm_close", self.gesture_config.weight_palm_close),
                            weight_palm_variance=gc.get("weight_palm_variance", self.gesture_config.weight_palm_variance),
                            weight_motion=gc.get("weight_motion", self.gesture_config.weight_motion),
                            weight_oscillation=gc.get("weight_oscillation", self.gesture_config.weight_oscillation),
                        )
                        self.gesture_classifier = GestureClassifier(config=self.gesture_config)
                        logger.info("Loaded gesture config from backend")
                else:
                    logger.warning(
                        f"Backend config not available (HTTP {resp.status_code}), using defaults"
                    )
        except Exception as e:
            logger.warning(f"Could not fetch backend config: {e}, using defaults")

    async def _send_heartbeat(self, fps: float):
        """Send a heartbeat to the backend to indicate this camera is alive."""
        payload = {
            "camera_id": self.camera_id,
            "or_number": self.or_number,
            "status": "ONLINE",
            "fps": round(fps, 2),
            "frame_count": self.frame_count,
            "tracked_persons": len(self.tracked_persons),
            "timestamp": datetime.utcnow().isoformat(),
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{self.backend_url}/api/v1/cameras/heartbeat",
                    json=payload
                )
                if resp.status_code == 200:
                    logger.debug(f"Heartbeat sent successfully for {self.camera_id}")
                else:
                    logger.warning(f"Heartbeat returned HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"Failed to send heartbeat: {e}")

    def run(self):
        """Run the CV pipeline"""

        # Determine video source (file or camera)
        if self.video_path:
            logger.info(f"Opening video file: {self.video_path}")
            source = self.video_path
        else:
            logger.info(f"Opening camera source: {self.camera_source}")
            source = self.camera_source

        cap = cv2.VideoCapture(source)

        if not cap.isOpened():
            logger.error(f"Failed to open video source: {source}")
            return

        # Get camera properties
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)

        logger.info(f"Camera: {width}x{height} @ {fps} FPS")

        # Initialize zone detector with camera resolution
        self.zone_detector = ZoneDetector(width, height)

        # Apply backend zone config if fetched at startup
        if self._backend_zones is not None:
            try:
                self.zone_detector.load_zones(self._backend_zones)
                logger.info("Applied backend zone config to zone detector")
            except AttributeError:
                logger.warning(
                    "ZoneDetector does not support load_zones(); backend zone config ignored"
                )
            except Exception as e:
                logger.warning(f"Failed to apply backend zone config: {e}")

        logger.info("Starting CV pipeline loop...")

        # For FPS calculation
        fps_start_time = time.time()
        fps_frame_count = 0
        current_fps = fps if fps > 0 else 30.0

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    # If video file ended
                    if self.video_path:
                        if self.loop_video:
                            logger.info("Video ended, looping...")
                            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            continue
                        else:
                            logger.info("Video ended")
                            break
                    else:
                        logger.warning("Failed to read frame from camera")
                        continue

                self.frame_count += 1
                fps_frame_count += 1

                # Calculate actual FPS every second
                elapsed_since_fps = time.time() - fps_start_time
                if elapsed_since_fps >= 1.0:
                    current_fps = fps_frame_count / elapsed_since_fps
                    fps_frame_count = 0
                    fps_start_time = time.time()

                # Run state expiry cleanup each frame
                removed_ids = self.state_machine.cleanup_expired()
                for pid in removed_ids:
                    if pid in self.tracked_persons:
                        del self.tracked_persons[pid]

                # Process frame
                processed_frame, events = self.process_frame(frame)

                # Publish events (only if case_id is set)
                if self.case_id and events:
                    for event in events:
                        asyncio.run(self.event_publisher.publish(event))

                # Sample frame for training data collection
                if self.frame_sampler:
                    self.frame_sampler.sample(
                        frame=frame,
                        frame_number=self.frame_count,
                        persons=self._last_persons,
                        state_machine=self.state_machine,
                        zone_detector=self.zone_detector,
                        gesture_classifier=self.gesture_classifier,
                    )

                # Send heartbeat every N seconds
                now = time.time()
                if now - self._last_heartbeat > self._heartbeat_interval:
                    asyncio.run(self._send_heartbeat(current_fps))
                    self._last_heartbeat = now

                # Display frame (skip in headless mode)
                if not self.headless:
                    window_title = "InfectionIQ CV Pipeline"
                    if self.video_path:
                        window_title += f" - {self.video_path.split('/')[-1].split(chr(92))[-1]}"
                    cv2.imshow(window_title, processed_frame)

                    # Control playback speed for video files (30 FPS)
                    wait_time = VIDEO_WAIT_TIME_MS if self.video_path else CAMERA_WAIT_TIME_MS

                    # Check for quit (q) or switch video (n)
                    key = cv2.waitKey(wait_time) & 0xFF
                    if key == ord('q'):
                        break
                    elif key == ord('n'):
                        # Allow switching to next video
                        logger.info("User requested next video")
                        break

        except KeyboardInterrupt:
            logger.info("Interrupted by user")

        finally:
            cap.release()
            cv2.destroyAllWindows()
            # Gracefully close the event publisher (flushes buffered events)
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self.event_publisher.close())
                loop.close()
            except Exception as e:
                logger.warning(f"Event publisher close error (events already sent): {e}")
            # Close frame sampler (writes final session metadata)
            if self.frame_sampler:
                self.frame_sampler.close()
            logger.info("CV Pipeline stopped")

    def run_calibration(self, output_dir: str = "."):
        """Run the CV pipeline in calibration mode for gesture threshold tuning.

        Press 's' to label current gesture as SANITIZING.
        Press 'n' to label current gesture as NOT_SANITIZING.
        Press 'q' to stop and save results.
        """
        from src.calibration.recorder import CalibrationRecorder
        import numpy as np

        recorder = CalibrationRecorder(config=self.gesture_config)
        logger.info("=== CALIBRATION MODE ===")
        logger.info("Press 's' = sanitizing, 'n' = not sanitizing, 'q' = quit & save")

        source = self.video_path if self.video_path else self.camera_source
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            logger.error(f"Failed to open video source: {source}")
            return

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.zone_detector = ZoneDetector(width, height)

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    if self.video_path and self.loop_video:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    break

                self.frame_count += 1

                # Detect persons and track hands
                persons = self.person_detector.detect(frame)
                current_result = None

                for person in persons:
                    person_id = person.track_id
                    x1, y1, x2, y2 = person.bbox
                    person_roi = frame[y1:y2, x1:x2]
                    if person_roi.size == 0:
                        continue

                    hands = self.hand_tracker.track(person_roi)
                    if not hands:
                        continue

                    for hand in hands:
                        hand.landmarks = [
                            (lm[0] * (x2 - x1) + x1, lm[1] * (y2 - y1) + y1, lm[2])
                            for lm in hand.landmarks
                        ]

                    self.gesture_classifier.update(person_id, hands)
                    current_result = self.gesture_classifier.classify(person_id)

                # Draw frame with gesture info
                processed = self._draw_visualizations(frame, persons)

                # Show calibration overlay
                if current_result:
                    info = (
                        f"Score: {current_result.score:.2f} | "
                        f"Palm: {current_result.palm_distance:.3f} | "
                        f"Osc: {current_result.oscillation_count} | "
                        f"Dur: {current_result.duration_sec:.1f}s"
                    )
                    cv2.putText(processed, info, (10, height - 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

                status = f"CALIBRATION | Samples: {len(recorder.session.samples)} | [s]=sanitize [n]=not [q]=quit"
                cv2.putText(processed, status, (10, height - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

                cv2.imshow("InfectionIQ Calibration", processed)

                wait_time = VIDEO_WAIT_TIME_MS if self.video_path else CAMERA_WAIT_TIME_MS
                key = cv2.waitKey(wait_time) & 0xFF

                if key == ord('q'):
                    break
                elif key in (ord('s'), ord('n')) and current_result:
                    label = "SANITIZING" if key == ord('s') else "NOT_SANITIZING"
                    recorder.record_sample(
                        label=label,
                        palm_distance=current_result.palm_distance,
                        palm_distance_var=0.0,  # Not tracked in GestureResult individually
                        avg_motion=current_result.motion_score,
                        oscillation_count=current_result.oscillation_count,
                        score=current_result.score,
                    )

        except KeyboardInterrupt:
            logger.info("Calibration interrupted")
        finally:
            cap.release()
            cv2.destroyAllWindows()
            saved_path = recorder.save(output_dir)
            logger.info(f"Calibration data saved to: {saved_path}")

    def process_frame(self, frame):
        """Process a single frame through the pipeline"""

        events = []

        # Stage 1: Person Detection
        persons = self.person_detector.detect(frame)
        self._last_persons = persons  # Store for frame sampler

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
            gesture_result = self.gesture_classifier.classify(person_id)
            is_sanitizing = gesture_result.is_sanitizing

            # New person detected → generate entry event
            if person_id not in self.tracked_persons:
                event = self._handle_entry(person_id, is_sanitizing, gesture_result)
                if event:
                    events.append(event)

            # Stage 5: Zone detection + state machine
            for hand in hands:
                palm_center = get_palm_center(hand.landmarks)
                zone = self.zone_detector.get_zone_from_pixel(
                    (int(palm_center[0]), int(palm_center[1]))
                )

                if is_sanitizing:
                    event = self._handle_sanitize(person_id, gesture_result)
                    if event:
                        events.append(event)
                elif zone.name not in ["DOOR", "SANITIZER"]:
                    # Only fire touch event when person enters a new zone
                    last_zone = self.tracked_persons.get(person_id, {}).get("last_zone")
                    if last_zone != zone.name:
                        event = self._handle_touch(person_id, zone, hand)
                        if event:
                            events.append(event)
                        if person_id in self.tracked_persons:
                            self.tracked_persons[person_id]["last_zone"] = zone.name

            # Update tracking
            if person_id not in self.tracked_persons:
                self.tracked_persons[person_id] = {
                    "state": "UNKNOWN",
                    "entry_time": datetime.utcnow(),
                    "hands": hands,
                    "sanitized": is_sanitizing,
                    "last_zone": None,
                }
            else:
                self.tracked_persons[person_id]["hands"] = hands
                # Update compliance: if person is ever seen sanitizing, mark them
                if is_sanitizing:
                    self.tracked_persons[person_id]["sanitized"] = True

        # Draw visualizations
        processed_frame = self._draw_visualizations(frame, persons)

        return processed_frame, events

    def _handle_entry(self, person_id: int, is_sanitizing: bool, gesture_result: GestureResult = None):
        """Handle person entry event"""

        compliant = is_sanitizing

        self.state_machine.on_entry(person_id)
        if is_sanitizing:
            self.state_machine.on_sanitize(person_id)

        event = {
            "type": "ENTRY",
            "data": {
                "case_id": self.case_id,
                "person_track_id": person_id,
                "timestamp": datetime.utcnow().isoformat(),
                "compliant": compliant,
                "sanitize_method": "SANITIZER" if compliant else "NONE",
            }
        }
        if gesture_result:
            event["data"]["gesture"] = {
                "score": gesture_result.score,
                "duration_sec": gesture_result.duration_sec,
                "palm_distance": gesture_result.palm_distance,
                "oscillation_count": gesture_result.oscillation_count,
            }
        return event

    def _handle_sanitize(self, person_id: int, gesture_result: GestureResult = None):
        """Handle sanitization event"""

        old_state = self.state_machine.get_state(person_id)
        new_state = self.state_machine.on_sanitize(person_id)

        event = {
            "type": "SANITIZE",
            "data": {
                "case_id": self.case_id,
                "person_track_id": person_id,
                "timestamp": datetime.utcnow().isoformat(),
                "state_before": old_state.value,
                "state_after": new_state.value,
            }
        }
        if gesture_result:
            event["data"]["gesture"] = {
                "score": gesture_result.score,
                "duration_sec": gesture_result.duration_sec,
                "palm_distance": gesture_result.palm_distance,
                "oscillation_count": gesture_result.oscillation_count,
            }
        return event

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
        return STATE_COLORS.get(state.value, (255, 255, 255))

    def _draw_hand_landmarks(self, frame, landmarks, color):
        """Draw hand landmarks on frame"""
        for i, lm in enumerate(landmarks):
            x, y = int(lm[0]), int(lm[1])
            cv2.circle(frame, (x, y), 3, color, -1)


def main():
    parser = argparse.ArgumentParser(description="InfectionIQ CV Pipeline")
    parser.add_argument("--camera", type=int, default=0, help="Camera source index")
    parser.add_argument("--video", type=str, help="Path to video file (instead of camera)")
    parser.add_argument("--no-loop", action="store_true", help="Don't loop video file")
    parser.add_argument("--backend", type=str, default=os.environ.get("INFECTIONIQ_BACKEND_URL", "http://localhost:8000"), help="Backend URL")
    parser.add_argument("--case-id", type=str, help="Active case ID")
    parser.add_argument("--or", type=str, default="OR-1", dest="or_number", help="OR number")
    parser.add_argument("--calibrate", action="store_true", help="Enter gesture calibration mode")
    parser.add_argument("--calibrate-output", type=str, default=".", help="Output directory for calibration data")
    parser.add_argument("--sample-frames", action="store_true", help="Enable training data collection (saves anonymized frames)")
    parser.add_argument("--sample-dir", type=str, default="./training_data", help="Output directory for sampled training frames")
    parser.add_argument("--headless", action="store_true", help="Run without GUI (for server-side video processing)")

    args = parser.parse_args()

    pipeline = CVPipeline(
        camera_source=args.camera,
        video_path=args.video,
        backend_url=args.backend,
        case_id=args.case_id,
        or_number=args.or_number,
        loop_video=not args.no_loop,
        sample_frames=args.sample_frames,
        sample_dir=args.sample_dir,
        headless=args.headless,
    )

    if args.calibrate:
        pipeline.run_calibration(output_dir=args.calibrate_output)
    else:
        pipeline.run()


if __name__ == "__main__":
    main()
