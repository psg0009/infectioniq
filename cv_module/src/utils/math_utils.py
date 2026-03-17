"""Shared math utilities for the CV module"""
import numpy as np
from typing import List, Tuple


PALM_INDICES = [0, 5, 9, 13, 17]


def get_palm_center(landmarks: List[Tuple[float, float, float]]) -> Tuple[float, float]:
    """Calculate palm center from hand landmarks."""
    palm_points = [landmarks[i] for i in PALM_INDICES if i < len(landmarks)]
    if not palm_points:
        return (0, 0)
    x = sum(p[0] for p in palm_points) / len(palm_points)
    y = sum(p[1] for p in palm_points) / len(palm_points)
    return (x, y)


def euclidean_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Calculate Euclidean distance between two 2D points."""
    return float(np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2))
