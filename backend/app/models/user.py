"""
User model for authentication
"""

from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
import uuid

from app.core.database import Base
from app.models.models import UUID36
from app.core.enums import UserRole, SubscriptionTier
from sqlalchemy import Enum as SQLEnum, Integer


class User(Base):
    """Application users (authentication)"""
    __tablename__ = "users"

    id = Column(UUID36(), primary_key=True, default=uuid.uuid4)
    supabase_id = Column(String(255), unique=True, nullable=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False, default="supabase-managed")
    full_name = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.VIEWER)
    subscription_tier = Column(
        SQLEnum(SubscriptionTier), nullable=False, default=SubscriptionTier.TRIAL
    )
    max_ors = Column(Integer, nullable=False, default=2)
    staff_id = Column(UUID36(), ForeignKey("staff.id"), nullable=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
