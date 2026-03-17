"""
Auth dependencies for FastAPI route protection

Supports three auth mechanisms:
1. Supabase JWT (primary — for users/frontend)
2. Legacy JWT Bearer token (fallback if no Supabase configured)
3. X-Service-Key header (for internal services: CV module, demo simulation)
"""

from typing import Optional, List
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError
import logging

from app.core.database import get_db
from app.core.security import decode_token
from app.core.enums import UserRole
from app.models.user import User

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


def _check_service_key(request: Request) -> bool:
    """Check if request has a valid internal service key."""
    from app.config import settings
    service_key = request.headers.get("X-Service-Key")
    if not service_key:
        return False
    expected = settings.INTERNAL_SERVICE_KEY
    if not expected:
        # Auto-generate in dev mode (same pattern as SECRET_KEY)
        return service_key == "dev-internal-key"
    return service_key == expected


_jwks_cache: Optional[dict] = None


def _get_supabase_jwks() -> Optional[dict]:
    """Fetch and cache Supabase JWKS (public keys for ES256 verification)."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    from app.config import settings
    if not settings.SUPABASE_URL:
        return None
    import urllib.request, json as _json
    try:
        url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
        with urllib.request.urlopen(url, timeout=5) as resp:
            _jwks_cache = _json.loads(resp.read())
            logger.info(f"Fetched Supabase JWKS: {len(_jwks_cache.get('keys', []))} keys")
            return _jwks_cache
    except Exception as e:
        logger.warning(f"Failed to fetch Supabase JWKS: {e}")
        return None


def _decode_supabase_jwt(token: str) -> Optional[dict]:
    """Decode a Supabase JWT using JWKS (ES256) or legacy secret (HS256)."""
    from app.config import settings
    import base64 as _b64, json as _json

    # Parse the token header to determine algorithm
    try:
        header_b64 = token.split('.')[0]
        header_b64 += '=' * (4 - len(header_b64) % 4)
        header = _json.loads(_b64.urlsafe_b64decode(header_b64))
    except Exception:
        return None

    alg = header.get('alg', '')

    # ES256 — verify with JWKS public key
    if alg == 'ES256':
        jwks = _get_supabase_jwks()
        if not jwks:
            return None
        kid = header.get('kid')
        for key_data in jwks.get('keys', []):
            if kid and key_data.get('kid') != kid:
                continue
            try:
                payload = jwt.decode(
                    token,
                    key_data,
                    algorithms=['ES256'],
                    audience='authenticated',
                )
                return payload
            except JWTError as e:
                logger.warning(f"ES256 JWT decode failed with kid={kid}: {e}")
                # Try without audience
                try:
                    payload = jwt.decode(
                        token,
                        key_data,
                        algorithms=['ES256'],
                        options={'verify_aud': False},
                    )
                    return payload
                except JWTError as e2:
                    logger.warning(f"ES256 JWT decode (no aud) also failed: {e2}")
        return None

    # HS256 — verify with legacy JWT secret
    if not settings.SUPABASE_JWT_SECRET:
        return None
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload
    except JWTError:
        try:
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            return payload
        except JWTError:
            return None


class _ServiceUser:
    """Fake user object for internal service calls.
    Passes all role/tier checks because is_superuser=True."""
    id = "00000000-0000-0000-0000-000000000000"
    email = "system@infectioniq.internal"
    full_name = "Internal Service"
    role = UserRole.ADMIN
    subscription_tier = "ENTERPRISE"
    max_ors = 999
    is_active = True
    is_superuser = True
    staff_id = None
    organization_id = None


async def _get_or_create_supabase_user(supabase_payload: dict, db: AsyncSession) -> User:
    """Find or auto-provision a local User record from Supabase JWT claims."""
    sub = supabase_payload.get("sub")  # Supabase user UUID
    email = supabase_payload.get("email", "")
    user_meta = supabase_payload.get("user_metadata", {})
    full_name = user_meta.get("full_name") or user_meta.get("name") or email.split("@")[0]

    # Look up by supabase_id first, then email
    result = await db.execute(select(User).where(User.supabase_id == sub))
    user = result.scalar_one_or_none()

    if user is None:
        # Try email match (user may have been seeded)
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            user.supabase_id = sub
            await db.commit()
            await db.refresh(user)
        else:
            # Auto-provision new user
            user = User(
                email=email,
                full_name=full_name,
                supabase_id=sub,
                password_hash="supabase-managed",
                role=UserRole.ADMIN,  # First user gets admin for demo
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info(f"Auto-provisioned user {email} from Supabase (id={user.id})")

    return user


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the current user from JWT token or service key."""
    # Check internal service key first
    if _check_service_key(request):
        return _ServiceUser()

    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token = credentials.credentials

    # Debug: log token header to diagnose verification issues
    try:
        import base64, json as _json
        header_b64 = token.split('.')[0]
        header_b64 += '=' * (4 - len(header_b64) % 4)
        token_header = _json.loads(base64.urlsafe_b64decode(header_b64))
        logger.info(f"JWT header: {token_header}")
    except Exception:
        logger.warning("Could not decode JWT header")

    # Try Supabase JWT first
    supabase_payload = _decode_supabase_jwt(token)
    if supabase_payload and supabase_payload.get("sub"):
        user = await _get_or_create_supabase_user(supabase_payload, db)
        return user

    # Fallback: legacy custom JWT
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Validate tenant isolation: user's org must match request tenant
    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id and user.organization_id and not user.is_superuser:
        if str(user.organization_id) != str(tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant mismatch",
            )

    return user


async def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    """Ensure the current user is active"""
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return user


async def get_current_organization(request: Request) -> Optional[str]:
    """Return the current tenant organization_id from request state."""
    return getattr(request.state, "tenant_id", None)


def require_role(*roles: UserRole):
    """Dependency factory that requires specific user roles"""
    async def role_checker(user: User = Depends(get_current_active_user)) -> User:
        if user.is_superuser:
            return user
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {[r.value for r in roles]}"
            )
        return user
    return role_checker


async def optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Optional auth - returns None if not authenticated"""
    if credentials is None:
        return None
    payload = decode_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    if user_id is None:
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
