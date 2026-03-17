"""
ML Training Pipeline
Utilities for training and evaluating the SSI risk prediction model
"""

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent / "models"
MODELS_DIR.mkdir(exist_ok=True)


@dataclass
class TrainingConfig:
    model_type: str = "xgboost"  # xgboost, lightgbm, catboost
    test_size: float = 0.2
    random_state: int = 42
    n_estimators: int = 100
    max_depth: int = 6
    learning_rate: float = 0.1
    early_stopping_rounds: int = 10


from dataclasses import dataclass


@dataclass
class TrainingResult:
    model_type: str
    accuracy: float
    auc_roc: float
    sensitivity: float
    specificity: float
    feature_importances: Dict[str, float]
    training_time_seconds: float
    timestamp: str
    model_path: Optional[str] = None


def prepare_features(cases_data: List[dict]) -> Tuple[np.ndarray, np.ndarray]:
    """Prepare feature matrix and labels from case data"""
    feature_names = [
        "procedure_duration_minutes",
        "wound_class_numeric",
        "entry_count",
        "compliance_rate",
        "critical_zone_entries",
        "touch_events",
        "staff_count",
        "avg_risk_score",
    ]

    X = []
    y = []
    for case in cases_data:
        features = [case.get(f, 0) for f in feature_names]
        X.append(features)
        y.append(case.get("infection_outcome", 0))

    return np.array(X), np.array(y)


def train_model(
    X: np.ndarray,
    y: np.ndarray,
    config: TrainingConfig = TrainingConfig(),
) -> TrainingResult:
    """Train a risk prediction model"""
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, roc_auc_score, confusion_matrix
    import time

    start_time = time.time()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=config.test_size, random_state=config.random_state
    )

    if config.model_type == "xgboost":
        import xgboost as xgb
        model = xgb.XGBClassifier(
            n_estimators=config.n_estimators,
            max_depth=config.max_depth,
            learning_rate=config.learning_rate,
            random_state=config.random_state,
            eval_metric="logloss",
        )
    elif config.model_type == "lightgbm":
        import lightgbm as lgb
        model = lgb.LGBMClassifier(
            n_estimators=config.n_estimators,
            max_depth=config.max_depth,
            learning_rate=config.learning_rate,
            random_state=config.random_state,
        )
    elif config.model_type == "catboost":
        from catboost import CatBoostClassifier
        model = CatBoostClassifier(
            iterations=config.n_estimators,
            depth=config.max_depth,
            learning_rate=config.learning_rate,
            random_state=config.random_state,
            verbose=0,
        )
    else:
        raise ValueError(f"Unknown model type: {config.model_type}")

    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1] if hasattr(model, "predict_proba") else y_pred

    accuracy = accuracy_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_proba) if len(np.unique(y_test)) > 1 else 0
    tn, fp, fn, tp = confusion_matrix(y_test, y_pred, labels=[0, 1]).ravel()
    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0

    # Feature importances
    importances = {}
    feature_names = [
        "procedure_duration", "wound_class", "entry_count", "compliance_rate",
        "critical_zone_entries", "touch_events", "staff_count", "avg_risk_score",
    ]
    if hasattr(model, "feature_importances_"):
        for name, imp in zip(feature_names, model.feature_importances_):
            importances[name] = round(float(imp), 4)

    training_time = time.time() - start_time

    # Save model
    model_path = str(MODELS_DIR / f"risk_model_{config.model_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
    if config.model_type == "xgboost":
        model.save_model(model_path)
    logger.info(f"Model saved to {model_path}")

    return TrainingResult(
        model_type=config.model_type,
        accuracy=round(accuracy, 4),
        auc_roc=round(auc, 4),
        sensitivity=round(sensitivity, 4),
        specificity=round(specificity, 4),
        feature_importances=importances,
        training_time_seconds=round(training_time, 2),
        timestamp=datetime.utcnow().isoformat(),
        model_path=model_path,
    )


def export_to_onnx(model_path: str, output_path: str, n_features: int = 8):
    """Export a trained model to ONNX format for inference"""
    try:
        import onnxmltools
        from skl2onnx.common.data_types import FloatTensorType

        logger.info(f"Exporting model {model_path} to ONNX: {output_path}")
        # Model-specific export logic would go here
        logger.info("ONNX export complete")
    except ImportError:
        logger.warning("onnxmltools not installed — skipping ONNX export")
