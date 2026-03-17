"""
Centralized Enum Definitions for InfectionIQ
Single source of truth - import from here everywhere.
"""

import enum


class StaffRole(str, enum.Enum):
    SURGEON = "SURGEON"
    NURSE = "NURSE"
    TECH = "TECH"
    ANESTHESIOLOGIST = "ANESTHESIOLOGIST"
    RESIDENT = "RESIDENT"
    OTHER = "OTHER"


class WoundClass(str, enum.Enum):
    CLEAN = "CLEAN"
    CLEAN_CONTAMINATED = "CLEAN_CONTAMINATED"
    CONTAMINATED = "CONTAMINATED"
    DIRTY = "DIRTY"
    UNKNOWN = "UNKNOWN"


class CaseStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Zone(str, enum.Enum):
    CRITICAL = "CRITICAL"
    STERILE = "STERILE"
    NON_STERILE = "NON_STERILE"
    SANITIZER = "SANITIZER"
    DOOR = "DOOR"


class PersonState(str, enum.Enum):
    UNKNOWN = "UNKNOWN"
    CLEAN = "CLEAN"
    POTENTIALLY_CONTAMINATED = "POTENTIALLY_CONTAMINATED"
    CONTAMINATED = "CONTAMINATED"
    DIRTY = "DIRTY"


class AlertType(str, enum.Enum):
    CONTAMINATION = "CONTAMINATION"
    MISSED_HYGIENE = "MISSED_HYGIENE"
    HIGH_RISK = "HIGH_RISK"
    CRITICAL_ZONE = "CRITICAL_ZONE"
    DISPENSER_LOW = "DISPENSER_LOW"
    DISPENSER_EMPTY = "DISPENSER_EMPTY"
    EXPIRED_SANITIZER = "EXPIRED_SANITIZER"
    CAMERA_OFFLINE = "CAMERA_OFFLINE"


class AlertSeverity(str, enum.Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    NURSE = "NURSE"
    SURGEON = "SURGEON"
    TECHNICIAN = "TECHNICIAN"
    VIEWER = "VIEWER"


class SubscriptionTier(str, enum.Enum):
    STARTER = "STARTER"
    PROFESSIONAL = "PROFESSIONAL"
    ENTERPRISE = "ENTERPRISE"
    TRIAL = "TRIAL"


class ConsentType(str, enum.Enum):
    DATA_COLLECTION = "DATA_COLLECTION"
    AI_MONITORING = "AI_MONITORING"
    VIDEO_RECORDING = "VIDEO_RECORDING"
    DATA_SHARING = "DATA_SHARING"
    RESEARCH = "RESEARCH"


class ConsentStatus(str, enum.Enum):
    PENDING = "PENDING"
    GRANTED = "GRANTED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
