"""Shared types for the CV module"""
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple


class PersonState(Enum):
    UNKNOWN = "UNKNOWN"
    CLEAN = "CLEAN"
    POTENTIALLY_CONTAMINATED = "POTENTIALLY_CONTAMINATED"
    CONTAMINATED = "CONTAMINATED"
    DIRTY = "DIRTY"


class Zone(Enum):
    DOOR = "DOOR"
    SANITIZER = "SANITIZER"
    NON_STERILE = "NON_STERILE"
    STERILE = "STERILE"
    CRITICAL = "CRITICAL"


@dataclass
class HandLandmarks:
    landmarks: List[Tuple[float, float, float]]
    handedness: str
    confidence: float
