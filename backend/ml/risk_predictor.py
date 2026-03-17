"""
Risk Prediction Module for InfectionIQ
Predicts surgical site infection risk based on case factors
"""
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False


class RiskPredictor:
    """Predicts infection risk for surgical cases"""

    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.model_loaded = False

        if model_path and Path(model_path).exists():
            self._load_model(model_path)
        else:
            logger.info("No trained model found - using rule-based predictions")

    def _load_model(self, model_path: str):
        """Load ONNX model"""
        if not ONNX_AVAILABLE:
            logger.warning("onnxruntime not available, using rule-based predictions")
            return

        try:
            self.model = ort.InferenceSession(model_path)
            self.model_loaded = True
            logger.info(f"Loaded risk model from {model_path}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")

    def predict(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict infection risk for a surgical case

        Args:
            case_data: Dictionary containing case factors:
                - procedure_type: str
                - wound_class: str (CLEAN, CLEAN_CONTAMINATED, CONTAMINATED, DIRTY)
                - duration_hrs: float
                - emergency_flag: bool
                - implant_flag: bool
                - complexity_score: int (1-10)

        Returns:
            Dictionary with:
                - score: int (0-100)
                - risk_level: str (LOW, MODERATE, HIGH, CRITICAL)
                - factors: List of contributing factors
                - recommendations: List of recommendations
        """
        if self.model_loaded:
            return self._predict_ml(case_data)
        else:
            return self._predict_rules(case_data)

    def _predict_ml(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """Predict using trained ML model"""
        # Feature extraction
        features = self._extract_features(case_data)

        # Run inference
        input_name = self.model.get_inputs()[0].name
        output_name = self.model.get_outputs()[0].name

        result = self.model.run([output_name], {input_name: features})[0]
        score = int(result[0] * 100)

        return self._format_result(score, case_data)

    def _predict_rules(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """Rule-based prediction (fallback when no model)"""
        score = 20  # Base score
        factors = []

        # Wound class factor
        wound_class = case_data.get("wound_class", "UNKNOWN")
        wound_scores = {
            "CLEAN": 0,
            "CLEAN_CONTAMINATED": 15,
            "CONTAMINATED": 30,
            "DIRTY": 45,
            "UNKNOWN": 10
        }
        wound_add = wound_scores.get(wound_class, 10)
        if wound_add > 0:
            score += wound_add
            factors.append(f"Wound class: {wound_class} (+{wound_add})")

        # Duration factor
        duration = case_data.get("duration_hrs", 0) or case_data.get("expected_duration_hrs", 1)
        if duration > 4:
            add = min(20, int((duration - 4) * 5))
            score += add
            factors.append(f"Extended duration: {duration}hrs (+{add})")

        # Emergency factor
        if case_data.get("emergency_flag"):
            score += 10
            factors.append("Emergency procedure (+10)")

        # Implant factor
        if case_data.get("implant_flag"):
            score += 15
            factors.append("Implant procedure (+15)")

        # Complexity factor
        complexity = case_data.get("complexity_score", 5)
        if complexity > 7:
            add = (complexity - 7) * 5
            score += add
            factors.append(f"High complexity: {complexity}/10 (+{add})")

        score = min(100, max(0, score))
        return self._format_result(score, case_data, factors)

    def _extract_features(self, case_data: Dict[str, Any]) -> Any:
        """Extract features for ML model"""
        if not NUMPY_AVAILABLE:
            return None

        wound_encoding = {
            "CLEAN": [1, 0, 0, 0],
            "CLEAN_CONTAMINATED": [0, 1, 0, 0],
            "CONTAMINATED": [0, 0, 1, 0],
            "DIRTY": [0, 0, 0, 1]
        }

        wound_class = case_data.get("wound_class", "CLEAN")
        wound_vec = wound_encoding.get(wound_class, [0.25, 0.25, 0.25, 0.25])

        features = [
            case_data.get("duration_hrs", 1) or 1,
            1 if case_data.get("emergency_flag") else 0,
            1 if case_data.get("implant_flag") else 0,
            case_data.get("complexity_score", 5) / 10,
            *wound_vec
        ]

        return np.array([features], dtype=np.float32)

    def _format_result(
        self,
        score: int,
        case_data: Dict[str, Any],
        factors: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Format prediction result"""
        # Determine risk level
        if score <= 25:
            risk_level = "LOW"
        elif score <= 50:
            risk_level = "MODERATE"
        elif score <= 75:
            risk_level = "HIGH"
        else:
            risk_level = "CRITICAL"

        # Generate recommendations
        recommendations = []

        if risk_level in ["HIGH", "CRITICAL"]:
            recommendations.append("Enhanced sterile protocol recommended")
            recommendations.append("Increase hand hygiene monitoring frequency")

        if case_data.get("implant_flag"):
            recommendations.append("Ensure laminar airflow in OR")

        wound_class = case_data.get("wound_class", "")
        if wound_class in ["CONTAMINATED", "DIRTY"]:
            recommendations.append("Consider prophylactic antibiotics per protocol")

        if case_data.get("duration_hrs", 0) > 4:
            recommendations.append("Schedule additional scrub breaks for team")

        if not recommendations:
            recommendations.append("Standard infection prevention protocols apply")

        return {
            "score": score,
            "risk_level": risk_level,
            "factors": factors or [],
            "recommendations": recommendations,
            "model_version": "1.0-rules" if not self.model_loaded else "1.0-ml"
        }


# Singleton instance
_predictor: Optional[RiskPredictor] = None


def get_risk_predictor(model_path: Optional[str] = None) -> RiskPredictor:
    """Get or create risk predictor instance"""
    global _predictor
    if _predictor is None:
        _predictor = RiskPredictor(model_path)
    return _predictor
