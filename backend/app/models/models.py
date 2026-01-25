"""
SQLAlchemy ORM Models for InfectionIQ
MySQL Compatible Version
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime,
    ForeignKey, Text, JSON, Enum as SQLEnum, CheckConstraint, CHAR
)
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator
import uuid
import enum

from app.core.database import Base


# Cross-database UUID type (stores as CHAR(36) in MySQL)
class UUID36(TypeDecorator):
    """Platform-independent UUID type using CHAR(36)"""
    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return uuid.UUID(value)
        return value


# =============================================================================
# ENUMS
# =============================================================================

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


class AlertSeverity(str, enum.Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# =============================================================================
# MODELS
# =============================================================================

class Staff(Base):
    """Staff members (surgeons, nurses, techs, etc.)"""
    __tablename__ = "staff"
    
    id = Column(UUID36(), primary_key=True, default=uuid.uuid4)
    employee_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(SQLEnum(StaffRole), nullable=False)
    department = Column(String(100))
    badge_id = Column(String(50))
    email = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    cases_as_surgeon = relationship("SurgicalCase", back_populates="surgeon")
    entry_exit_events = relationship("EntryExitEvent", back_populates="staff")
    alerts = relationship("Alert", back_populates="staff", foreign_keys="Alert.staff_id")


class Team(Base):
    """Surgical teams"""
    __tablename__ = "teams"
    
    id = Column(UUID36(), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    department = Column(String(100))
    lead_id = Column(UUID36(), ForeignKey("staff.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    cases = relationship("SurgicalCase", back_populates="team")
    members = relationship("TeamMember", back_populates="team")


class TeamMember(Base):
    """Team membership"""
    __tablename__ = "team_members"
    
    team_id = Column(UUID36(), ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
    staff_id = Column(UUID36(), ForeignKey("staff.id", ondelete="CASCADE"), primary_key=True)
    role_in_team = Column(String(50), default="MEMBER")
    joined_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    team = relationship("Team", back_populates="members")
    staff = relationship("Staff")


class SurgicalCase(Base):
    """Surgical cases"""
    __tablename__ = "surgical_cases"
    
    id = Column(UUID36(), primary_key=True, default=uuid.uuid4)
    or_number = Column(String(20), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    procedure_type = Column(String(100), nullable=False)
    procedure_code = Column(String(20))
    surgeon_id = Column(UUID36(), ForeignKey("staff.id"))
    team_id = Column(UUID36(), ForeignKey("teams.id"))
    patient_id = Column(String(50))
    wound_class = Column(SQLEnum(WoundClass))
    expected_duration_hrs = Column(Float)
    actual_duration_hrs = Column(Float)
    complexity_score = Column(Integer)
    implant_flag = Column(Boolean, default=False)
    emergency_flag = Column(Boolean, default=False)
    status = Column(SQLEnum(CaseStatus), default=CaseStatus.SCHEDULED)
    outcome = Column(String(50))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    surgeon = relationship("Staff", back_populates="cases_as_surgeon")
    team = relationship("Team", back_populates="cases")
    risk_score = relationship("RiskScore", back_populates="case", uselist=False)
    entry_exit_events = relationship("EntryExitEvent", back_populates="case")
    alerts = relationship("Alert", back_populates="case")


class RiskScore(Base):
    """Pre-surgery risk predictions"""
    __tablename__ = "risk_scores"
    
    case_id = Column(UUID36(), ForeignKey("surgical_cases.id", ondelete="CASCADE"), primary_key=True)
    score = Column(Integer, nullable=False)
    risk_level = Column(SQLEnum(RiskLevel), nullable=False)
    factors = Column(JSON)
    recommendations = Column(JSON)
    model_version = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Constraints
    __table_args__ = (
        CheckConstraint('score >= 0 AND score <= 100', name='risk_score_range'),
    )
    
    # Relationships
    case = relationship("SurgicalCase", back_populates="risk_score")


class EntryExitEvent(Base):
    """Entry/Exit events with compliance status"""
    __tablename__ = "entry_exit_events"
    
    id = Column(UUID36(), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID36(), ForeignKey("surgical_cases.id", ondelete="CASCADE"))
    staff_id = Column(UUID36(), ForeignKey("staff.id"))
    person_track_id = Column(Integer)
    event_type = Column(String(20), nullable=False)  # ENTRY, EXIT
    timestamp = Column(DateTime, nullable=False)
    compliant = Column(Boolean, nullable=False)
    sanitize_method = Column(String(30))  # HAND_WASH, SANITIZER, BOTH, NONE
    sanitize_duration_sec = Column(Float)
    sanitize_volume_ml = Column(Float)
    confidence = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    case = relationship("SurgicalCase", back_populates="entry_exit_events")
    staff = relationship("Staff", back_populates="entry_exit_events")


class TouchEvent(Base):
    """Touch events (high frequency, stored in TimescaleDB)"""
    __tablename__ = "touch_events"
    
    id = Column(UUID36(), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID36(), nullable=False)
    staff_id = Column(UUID36())
    person_track_id = Column(Integer)
    timestamp = Column(DateTime, nullable=False)
    zone = Column(SQLEnum(Zone), nullable=False)
    surface = Column(String(50))
    hand = Column(String(10))  # LEFT, RIGHT, BOTH
    person_state_before = Column(String(30))
    person_state_after = Column(String(30))
    risk_level = Column(Integer)
    hand_position_x = Column(Float)
    hand_position_y = Column(Float)
    confidence = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    """System alerts"""
    __tablename__ = "alerts"
    
    id = Column(UUID36(), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID36(), ForeignKey("surgical_cases.id", ondelete="CASCADE"))
    staff_id = Column(UUID36(), ForeignKey("staff.id"))
    touch_event_id = Column(UUID36())
    alert_type = Column(SQLEnum(AlertType), nullable=False)
    severity = Column(SQLEnum(AlertSeverity), nullable=False)
    message = Column(Text)
    acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(UUID36(), ForeignKey("staff.id"))
    acknowledged_at = Column(DateTime)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime)
    timestamp = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    case = relationship("SurgicalCase", back_populates="alerts")
    staff = relationship("Staff", back_populates="alerts", foreign_keys=[staff_id])


class Dispenser(Base):
    """Sanitizer dispensers"""
    __tablename__ = "dispensers"
    
    id = Column(UUID36(), primary_key=True, default=uuid.uuid4)
    dispenser_id = Column(String(50), unique=True, nullable=False)
    or_number = Column(String(20), nullable=False)
    location_description = Column(String(255))
    dispenser_type = Column(String(50))  # WALL_MOUNT, STAND, PORTABLE
    capacity_ml = Column(Integer, default=1200)
    installed_at = Column(DateTime)
    last_maintenance = Column(DateTime)
    status = Column(String(20), default="ACTIVE")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    current_status = relationship("DispenserStatus", back_populates="dispenser", uselist=False)


class DispenserStatus(Base):
    """Real-time dispenser status"""
    __tablename__ = "dispenser_status"
    
    dispenser_id = Column(String(50), ForeignKey("dispensers.dispenser_id", ondelete="CASCADE"), primary_key=True)
    level_percent = Column(Float, nullable=False)
    level_ml = Column(Float)
    status = Column(String(20), nullable=False)  # OK, WARNING, LOW, CRITICAL, EMPTY, OFFLINE
    last_dispense_time = Column(DateTime)
    dispenses_today = Column(Integer, default=0)
    volume_today_ml = Column(Float, default=0)
    avg_volume_per_dispense = Column(Float)
    estimated_empty_time = Column(DateTime)
    battery_percent = Column(Float)
    cartridge_id = Column(String(50))
    cartridge_type = Column(String(100))
    cartridge_installed_at = Column(DateTime)
    cartridge_expiration_date = Column(DateTime)
    days_until_expiration = Column(Integer)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    dispenser = relationship("Dispenser", back_populates="current_status")


class DispenseEvent(Base):
    """Individual dispense events"""
    __tablename__ = "dispense_events"
    
    id = Column(UUID36(), primary_key=True, default=uuid.uuid4)
    dispenser_id = Column(String(50), nullable=False)
    case_id = Column(UUID36())
    staff_id = Column(UUID36())
    volume_ml = Column(Float, nullable=False)
    is_valid_sanitization = Column(Boolean)
    level_before = Column(Float)
    level_after = Column(Float)
    timestamp = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class InfectionOutcome(Base):
    """Infection outcomes for ML training"""
    __tablename__ = "infection_outcomes"
    
    id = Column(UUID36(), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID36(), ForeignKey("surgical_cases.id", ondelete="CASCADE"))
    infection_detected = Column(Boolean, nullable=False)
    infection_date = Column(DateTime)
    infection_type = Column(String(100))
    organism = Column(String(100))
    severity = Column(String(20))
    notes = Column(Text)
    reported_by = Column(UUID36(), ForeignKey("staff.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
