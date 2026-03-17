"""
Pydantic Schemas for API Request/Response Validation
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, UUID4

from app.core.enums import (
    StaffRole, WoundClass, CaseStatus, RiskLevel,
    Zone, PersonState, AlertType, AlertSeverity
)


# =============================================================================
# BASE SCHEMAS
# =============================================================================

class BaseSchema(BaseModel):
    """Base schema with common config"""
    class Config:
        from_attributes = True
        use_enum_values = True


# =============================================================================
# STAFF SCHEMAS
# =============================================================================

class StaffCreate(BaseModel):
    employee_id: str = Field(..., max_length=50)
    name: str = Field(..., max_length=255)
    role: StaffRole
    department: Optional[str] = Field(None, max_length=100)
    badge_id: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = None


class StaffUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    role: Optional[StaffRole] = None
    department: Optional[str] = Field(None, max_length=100)
    badge_id: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = None
    is_active: Optional[bool] = None


class StaffResponse(BaseSchema):
    id: UUID4
    employee_id: str
    name: str
    role: StaffRole
    department: Optional[str]
    badge_id: Optional[str]
    email: Optional[str]
    is_active: bool
    created_at: datetime


class StaffComplianceResponse(BaseSchema):
    staff: StaffResponse
    compliance_rate_7d: float
    compliance_rate_30d: float
    total_entries: int
    violations: int
    last_activity: Optional[datetime]


# =============================================================================
# TEAM SCHEMAS
# =============================================================================

class TeamCreate(BaseModel):
    name: str = Field(..., max_length=255)
    department: Optional[str] = Field(None, max_length=100)
    lead_id: Optional[UUID4] = None


class TeamResponse(BaseSchema):
    id: UUID4
    name: str
    department: Optional[str]
    lead_id: Optional[UUID4]
    created_at: datetime
    member_count: Optional[int] = None


class TeamComplianceResponse(BaseSchema):
    team: TeamResponse
    compliance_rate_7d: float
    compliance_rate_30d: float
    infection_count_90d: int
    members: List[StaffComplianceResponse]


# =============================================================================
# CASE SCHEMAS
# =============================================================================

class CaseCreate(BaseModel):
    or_number: str = Field(..., max_length=20)
    start_time: datetime
    procedure_type: str = Field(..., max_length=100)
    procedure_code: Optional[str] = Field(None, max_length=20)
    surgeon_id: Optional[UUID4] = None
    team_id: Optional[UUID4] = None
    patient_id: Optional[str] = Field(None, max_length=50)
    wound_class: Optional[WoundClass] = None
    expected_duration_hrs: Optional[float] = None
    complexity_score: Optional[int] = Field(None, ge=1, le=5)
    implant_flag: bool = False
    emergency_flag: bool = False


class CaseUpdate(BaseModel):
    end_time: Optional[datetime] = None
    status: Optional[CaseStatus] = None
    outcome: Optional[str] = None
    notes: Optional[str] = None


class RiskScoreResponse(BaseSchema):
    model_config = {"protected_namespaces": ()}

    score: int = Field(..., ge=0, le=100)
    risk_level: RiskLevel
    factors: Optional[List[str]] = None
    recommendations: Optional[List[str]] = None
    model_version: Optional[str] = None
    created_at: datetime


class CaseResponse(BaseSchema):
    id: UUID4
    or_number: str
    start_time: datetime
    end_time: Optional[datetime]
    procedure_type: str
    procedure_code: Optional[str]
    surgeon_id: Optional[UUID4]
    team_id: Optional[UUID4]
    patient_id: Optional[str]
    wound_class: Optional[WoundClass]
    expected_duration_hrs: Optional[float]
    actual_duration_hrs: Optional[float]
    complexity_score: Optional[int]
    implant_flag: bool
    emergency_flag: bool
    status: CaseStatus
    outcome: Optional[str]
    created_at: datetime


class CaseWithRiskResponse(CaseResponse):
    risk_score: Optional[RiskScoreResponse] = None


class CaseComplianceResponse(BaseSchema):
    case_id: UUID4
    overall_compliance_rate: float
    total_entries: int
    compliant_entries: int
    total_touches: int
    contamination_events: int
    alerts_count: int
    staff_compliance: List[Dict[str, Any]]


# =============================================================================
# COMPLIANCE EVENT SCHEMAS
# =============================================================================

class EntryEventCreate(BaseModel):
    case_id: UUID4
    staff_id: Optional[UUID4] = None
    person_track_id: Optional[int] = None
    timestamp: datetime
    compliant: bool
    sanitize_method: Optional[str] = None
    sanitize_duration_sec: Optional[float] = None
    sanitize_volume_ml: Optional[float] = None
    confidence: Optional[float] = None


class ExitEventCreate(BaseModel):
    case_id: UUID4
    staff_id: Optional[UUID4] = None
    person_track_id: Optional[int] = None
    timestamp: datetime


class EntryExitEventResponse(BaseSchema):
    id: UUID4
    case_id: UUID4
    staff_id: Optional[UUID4]
    person_track_id: Optional[int]
    event_type: str
    timestamp: datetime
    compliant: bool
    sanitize_method: Optional[str]
    sanitize_duration_sec: Optional[float]
    sanitize_volume_ml: Optional[float]
    confidence: Optional[float]


class TouchEventCreate(BaseModel):
    case_id: UUID4
    staff_id: Optional[UUID4] = None
    person_track_id: Optional[int] = None
    timestamp: datetime
    zone: Zone
    surface: Optional[str] = None
    hand: Optional[str] = None
    position: Optional[Dict[str, float]] = None
    confidence: Optional[float] = None


class TouchEventResponse(BaseSchema):
    id: UUID4
    case_id: UUID4
    staff_id: Optional[UUID4]
    timestamp: datetime
    zone: Zone
    surface: Optional[str]
    hand: Optional[str]
    person_state_before: Optional[str]
    person_state_after: Optional[str]
    risk_level: Optional[int]


class StateChangeResponse(BaseModel):
    before: PersonState
    after: PersonState


class TouchEventWithStateResponse(BaseModel):
    event_id: UUID4
    state_change: StateChangeResponse
    alert_generated: Optional[Dict[str, Any]] = None


# =============================================================================
# ALERT SCHEMAS
# =============================================================================

class AlertCreate(BaseModel):
    case_id: UUID4
    staff_id: Optional[UUID4] = None
    touch_event_id: Optional[UUID4] = None
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    timestamp: datetime


class AlertResponse(BaseSchema):
    id: UUID4
    case_id: UUID4
    staff_id: Optional[UUID4]
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    acknowledged: bool
    acknowledged_at: Optional[datetime]
    resolved: bool
    resolved_at: Optional[datetime]
    timestamp: datetime
    created_at: datetime


class AlertAcknowledgeRequest(BaseModel):
    acknowledged_by: Optional[UUID4] = None


# =============================================================================
# RISK PREDICTION SCHEMAS
# =============================================================================

class RiskPredictionRequest(BaseModel):
    case_id: Optional[UUID4] = None
    or_number: str
    procedure_type: str
    surgeon_id: Optional[UUID4] = None
    team_id: Optional[UUID4] = None
    expected_duration_hrs: float
    wound_class: Optional[WoundClass] = None
    complexity_score: Optional[int] = Field(None, ge=1, le=5)
    implant_flag: bool = False
    emergency_flag: bool = False
    start_time: datetime


class RiskPredictionResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    score: int = Field(..., ge=0, le=100)
    risk_level: RiskLevel
    factors: List[Dict[str, Any]]
    recommendations: List[str]
    model_version: str


# =============================================================================
# DISPENSER SCHEMAS
# =============================================================================

class DispenserCreate(BaseModel):
    dispenser_id: str = Field(..., max_length=50)
    or_number: str = Field(..., max_length=20)
    location_description: Optional[str] = None
    dispenser_type: Optional[str] = None
    capacity_ml: int = 1200


class DispenserStatusResponse(BaseSchema):
    dispenser_id: str
    or_number: str
    location_description: Optional[str]
    level_percent: float
    level_ml: Optional[float]
    status: str
    last_dispense_time: Optional[datetime]
    dispenses_today: int
    volume_today_ml: float
    estimated_empty_time: Optional[datetime]
    cartridge_expiration_date: Optional[datetime]
    days_until_expiration: Optional[int]
    last_updated: datetime


class DispenseEventCreate(BaseModel):
    dispenser_id: str
    case_id: Optional[UUID4] = None
    staff_id: Optional[UUID4] = None
    volume_ml: float
    timestamp: datetime


class RefillRequest(BaseModel):
    cartridge_id: Optional[str] = None
    refill_level_percent: float = 100


# =============================================================================
# ANALYTICS SCHEMAS
# =============================================================================

class ComplianceTrendResponse(BaseModel):
    date: datetime
    compliance_rate: float
    total_entries: int
    compliant_entries: int


class TopViolationsResponse(BaseModel):
    violation_type: str
    count: int
    percentage: float


class DashboardMetricsResponse(BaseModel):
    active_cases: int
    overall_compliance_rate: float
    active_alerts: int
    critical_alerts: int
    dispensers_low: int
    today_entries: int
    today_violations: int


# =============================================================================
# WEBSOCKET SCHEMAS
# =============================================================================

class WebSocketMessage(BaseModel):
    type: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class EntryEventMessage(BaseModel):
    type: str = "ENTRY"
    event_id: UUID4
    staff_id: Optional[UUID4]
    staff_name: Optional[str]
    compliant: bool
    person_state: PersonState
    timestamp: datetime


class TouchEventMessage(BaseModel):
    type: str = "TOUCH"
    staff_name: Optional[str]
    zone: Zone
    surface: Optional[str]
    state_before: PersonState
    state_after: PersonState
    timestamp: datetime


class AlertEventMessage(BaseModel):
    type: str = "ALERT"
    alert_id: UUID4
    alert_type: AlertType
    severity: AlertSeverity
    staff_name: Optional[str]
    message: str
    timestamp: datetime


class ComplianceUpdateMessage(BaseModel):
    type: str = "COMPLIANCE_UPDATE"
    overall_rate: float
    current_staff_count: int
    clean_count: int
    contaminated_count: int
    timestamp: datetime
