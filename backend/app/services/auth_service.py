"""
Auth Service - registration, login, token management
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.models.user import User
from app.core.enums import UserRole
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_user(
        self, email: str, password: str, full_name: str, role: UserRole = UserRole.VIEWER
    ) -> User:
        # Check if email already exists
        result = await self.db.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none():
            raise ValueError("Email already registered")

        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role=role,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None or not verify_password(password, user.password_hash):
            return None
        # Update last login
        user.last_login = datetime.utcnow()
        await self.db.commit()
        return user

    def create_tokens(self, user: User) -> Dict[str, Any]:
        token_data = {"sub": str(user.id), "role": user.role.value}
        return {
            "access_token": create_access_token(token_data),
            "refresh_token": create_refresh_token(token_data),
            "token_type": "bearer",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value,
                "subscription_tier": user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else (user.subscription_tier or "TRIAL"),
                "max_ors": getattr(user, 'max_ors', 2) or 2,
                "staff_id": str(user.staff_id) if user.staff_id else None,
                "is_superuser": user.is_superuser,
            },
        }

    async def refresh_tokens(self, refresh_token_str: str) -> Optional[Dict[str, Any]]:
        payload = decode_token(refresh_token_str)
        if payload is None or payload.get("type") != "refresh":
            return None
        user_id = payload.get("sub")
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            return None
        return self.create_tokens(user)

    async def change_password(self, user: User, old_password: str, new_password: str) -> bool:
        if not verify_password(old_password, user.password_hash):
            return False
        user.password_hash = hash_password(new_password)
        await self.db.commit()
        return True
