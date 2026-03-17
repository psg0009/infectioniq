"""
Gesture Calibration Recorder
Captures labeled gesture samples for threshold tuning.

Usage:
    Run the CV pipeline with --calibrate flag, then press:
      's' -> label current gesture as SANITIZING
      'n' -> label current gesture as NOT_SANITIZING
      'q' -> stop calibration and save results
"""

import json
import time
import logging
import itertools
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from config import GestureConfig

logger = logging.getLogger(__name__)


@dataclass
class CalibrationSample:
    """A single labeled gesture sample with raw feature values."""
    timestamp: str
    label: str  # "SANITIZING" or "NOT_SANITIZING"
    palm_distance: float
    palm_distance_var: float
    avg_motion: float
    oscillation_count: int
    score: float
    person_id: int = 0


@dataclass
class CalibrationSession:
    """Collection of labeled samples from a calibration run."""
    session_id: str = ""
    started_at: str = ""
    ended_at: str = ""
    samples: List[CalibrationSample] = field(default_factory=list)
    config_used: Dict = field(default_factory=dict)


class CalibrationRecorder:
    """Records labeled gesture samples during calibration mode."""

    def __init__(self, config: Optional[GestureConfig] = None):
        self.config = config or GestureConfig()
        self.session = CalibrationSession(
            session_id=datetime.utcnow().strftime("%Y%m%d_%H%M%S"),
            started_at=datetime.utcnow().isoformat(),
            config_used=self._config_to_dict(self.config),
        )

    def record_sample(
        self,
        label: str,
        palm_distance: float,
        palm_distance_var: float,
        avg_motion: float,
        oscillation_count: int,
        score: float,
        person_id: int = 0,
    ):
        """Record a labeled sample."""
        sample = CalibrationSample(
            timestamp=datetime.utcnow().isoformat(),
            label=label,
            palm_distance=palm_distance,
            palm_distance_var=palm_distance_var,
            avg_motion=avg_motion,
            oscillation_count=oscillation_count,
            score=score,
            person_id=person_id,
        )
        self.session.samples.append(sample)
        logger.info(
            f"Recorded {label} sample: score={score:.3f}, "
            f"palm_dist={palm_distance:.4f}, motion={avg_motion:.4f}, "
            f"osc={oscillation_count}"
        )

    def save(self, output_dir: str = ".") -> str:
        """Save calibration session to JSON file. Returns the file path."""
        self.session.ended_at = datetime.utcnow().isoformat()
        output_path = Path(output_dir) / f"calibration_{self.session.session_id}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "session_id": self.session.session_id,
            "started_at": self.session.started_at,
            "ended_at": self.session.ended_at,
            "config_used": self.session.config_used,
            "total_samples": len(self.session.samples),
            "sanitizing_count": sum(
                1 for s in self.session.samples if s.label == "SANITIZING"
            ),
            "not_sanitizing_count": sum(
                1 for s in self.session.samples if s.label == "NOT_SANITIZING"
            ),
            "samples": [asdict(s) for s in self.session.samples],
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved {len(self.session.samples)} samples to {output_path}")
        return str(output_path)

    @staticmethod
    def load_samples(file_path: str) -> List[CalibrationSample]:
        """Load calibration samples from a JSON file."""
        with open(file_path) as f:
            data = json.load(f)
        return [CalibrationSample(**s) for s in data["samples"]]

    @staticmethod
    def _config_to_dict(config: GestureConfig) -> dict:
        return {
            "palm_distance_threshold": config.palm_distance_threshold,
            "palm_variance_threshold": config.palm_variance_threshold,
            "motion_threshold": config.motion_threshold,
            "oscillation_threshold": config.oscillation_threshold,
            "score_threshold": config.score_threshold,
            "min_duration_sec": config.min_duration_sec,
            "weight_palm_close": config.weight_palm_close,
            "weight_palm_variance": config.weight_palm_variance,
            "weight_motion": config.weight_motion,
            "weight_oscillation": config.weight_oscillation,
        }


def sweep_thresholds(
    samples: List[CalibrationSample],
    palm_dist_range: Optional[List[float]] = None,
    motion_range: Optional[List[float]] = None,
    oscillation_range: Optional[List[int]] = None,
    score_range: Optional[List[float]] = None,
) -> List[Dict]:
    """Test threshold combinations against labeled samples.

    Returns a list of dicts, each with threshold values and metrics
    (accuracy, sensitivity, specificity), sorted by accuracy descending.
    """
    if not samples:
        return []

    if palm_dist_range is None:
        palm_dist_range = [0.10, 0.12, 0.15, 0.18, 0.20]
    if motion_range is None:
        motion_range = [0.01, 0.015, 0.02, 0.025, 0.03]
    if oscillation_range is None:
        oscillation_range = [2, 3, 4, 5, 6]
    if score_range is None:
        score_range = [0.5, 0.6, 0.7, 0.8, 0.9]

    results = []

    for palm_t, motion_t, osc_t, score_t in itertools.product(
        palm_dist_range, motion_range, oscillation_range, score_range
    ):
        tp = tn = fp = fn = 0

        for sample in samples:
            # Recompute score with these thresholds (using default weights)
            s = 0.0
            if sample.palm_distance < palm_t:
                s += 0.3
            if sample.palm_distance_var > 0.001:
                s += 0.2
            if sample.avg_motion > motion_t:
                s += 0.2
            if sample.oscillation_count >= osc_t:
                s += 0.3

            predicted = s >= score_t
            actual = sample.label == "SANITIZING"

            if predicted and actual:
                tp += 1
            elif not predicted and not actual:
                tn += 1
            elif predicted and not actual:
                fp += 1
            else:
                fn += 1

        total = tp + tn + fp + fn
        accuracy = (tp + tn) / total if total > 0 else 0
        sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0

        results.append({
            "palm_distance_threshold": palm_t,
            "motion_threshold": motion_t,
            "oscillation_threshold": osc_t,
            "score_threshold": score_t,
            "accuracy": round(accuracy, 4),
            "sensitivity": round(sensitivity, 4),
            "specificity": round(specificity, 4),
            "true_positives": tp,
            "true_negatives": tn,
            "false_positives": fp,
            "false_negatives": fn,
        })

    results.sort(key=lambda r: r["accuracy"], reverse=True)
    return results
