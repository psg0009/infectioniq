"""
Auth API Endpoints - register, login, token refresh, profile
"""

import re
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.core.auth_deps import get_current_active_user
from app.core.enums import UserRole
from app.core.security_controls import login_tracker
from app.models.user import User
from app.services.auth_service import AuthService

router = APIRouter()


def _validate_password_complexity(password: str) -> str:
    """Validate password meets complexity requirements"""
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters")
    if settings.PASSWORD_REQUIRE_UPPERCASE and not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
    if settings.PASSWORD_REQUIRE_DIGIT and not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit")
    if settings.PASSWORD_REQUIRE_SPECIAL and not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        raise ValueError("Password must contain at least one special character")
    return password


# --- Schemas ---

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=1, max_length=255)
    role: UserRole = UserRole.VIEWER

    @field_validator("password")
    @classmethod
    def check_password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    subscription_tier: str = "TRIAL"
    max_ors: int = 2
    staff_id: str | None = None
    is_active: bool = True
    is_superuser: bool

    class Config:
        from_attributes = True


# --- Endpoints ---

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user"""
    service = AuthService(db)
    try:
        user = await service.register_user(
            email=request.email,
            password=request.password,
            full_name=request.full_name,
            role=request.role,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return service.create_tokens(user)


@router.post("/login")
async def login(request: LoginRequest, req: Request, db: AsyncSession = Depends(get_db)):
    """Login and receive JWT tokens"""
    client_ip = req.client.host if req.client else "unknown"
    identifier = f"{client_ip}:{request.email}"

    if login_tracker.is_locked(identifier):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Account temporarily locked due to too many failed attempts. Try again later.",
        )

    service = AuthService(db)
    user = await service.authenticate_user(request.email, request.password)
    if user is None:
        login_tracker.record_failure(identifier)
        remaining = login_tracker.remaining_attempts(identifier)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid email or password. {remaining} attempts remaining.",
        )

    login_tracker.record_success(identifier)
    return service.create_tokens(user)


@router.post("/refresh")
async def refresh(request: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Refresh access token using refresh token"""
    service = AuthService(db)
    tokens = await service.refresh_tokens(request.refresh_token)
    if tokens is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    return tokens


@router.get("/me", response_model=UserResponse)
async def get_profile(user: User = Depends(get_current_active_user)):
    """Get current user profile"""
    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role.value if hasattr(user.role, 'value') else user.role,
        subscription_tier=user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else (user.subscription_tier or "TRIAL"),
        max_ors=user.max_ors or 2,
        staff_id=str(user.staff_id) if user.staff_id else None,
        is_active=getattr(user, 'is_active', True),
        is_superuser=user.is_superuser,
    )


@router.put("/me", response_model=UserResponse)
async def update_profile(
    request: UpdateProfileRequest,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user profile"""
    if request.full_name is not None:
        user.full_name = request.full_name
    if request.email is not None:
        user.email = request.email
    await db.commit()
    await db.refresh(user)
    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role.value if hasattr(user.role, 'value') else user.role,
        subscription_tier=user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else (user.subscription_tier or "TRIAL"),
        max_ors=user.max_ors or 2,
        staff_id=str(user.staff_id) if user.staff_id else None,
        is_active=getattr(user, 'is_active', True),
        is_superuser=user.is_superuser,
    )


@router.post("/supabase-sync", response_model=UserResponse)
async def supabase_sync(user: User = Depends(get_current_active_user)):
    """Return user profile after Supabase auth (auto-provisions on first call via auth_deps)."""
    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role.value if hasattr(user.role, 'value') else user.role,
        subscription_tier=user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else (user.subscription_tier or "TRIAL"),
        max_ors=user.max_ors or 2,
        staff_id=str(user.staff_id) if user.staff_id else None,
        is_active=getattr(user, 'is_active', True),
        is_superuser=user.is_superuser,
    )


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Change own password"""
    service = AuthService(db)
    if not await service.change_password(user, request.old_password, request.new_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect current password")
    return {"status": "password_changed"}
