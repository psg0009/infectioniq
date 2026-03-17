"""
Patient Consent model
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy import Enum as SQLEnum
import uuid

from app.core.database import Base
from app.models.models import UUID36
from app.core.enums import ConsentType, ConsentStatus


class PatientConsent(Base):
    """Patient consent records for data collection and AI monitoring"""
    __tablename__ = "patient_consents"

    id = Column(UUID36(), primary_key=True, default=uuid.uuid4)
    patient_id = Column(String(50), nullable=False, index=True)
    case_id = Column(UUID36(), ForeignKey("surgical_cases.id"), nullable=True)
    consent_type = Column(SQLEnum(ConsentType), nullable=False)
    status = Column(SQLEnum(ConsentStatus), default=ConsentStatus.PENDING, nullable=False)
    consented_by = Column(String(255), nullable=False)  # patient or guardian name
    consented_at = Column(DateTime, nullable=True)
    witness_name = Column(String(255), nullable=True)
    witness_id = Column(UUID36(), ForeignKey("staff.id"), nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    revocation_reason = Column(Text, nullable=True)
    document_url = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
