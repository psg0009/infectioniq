"""
Audit Log model for HIPAA compliance
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, JSON, ForeignKey
import uuid

from app.core.database import Base
from app.models.models import UUID36


class AuditLog(Base):
    """Audit trail for all state-changing operations"""
    __tablename__ = "audit_logs"

    id = Column(UUID36(), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID36(), ForeignKey("users.id"), nullable=True)
    action = Column(String(50), nullable=False)  # CREATE, READ, UPDATE, DELETE
    resource_type = Column(String(100), nullable=False)  # e.g. "case", "alert", "staff"
    resource_id = Column(String(36), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
