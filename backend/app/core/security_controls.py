"""
SOC2 Security Controls
Implements security controls required for SOC2 Type II compliance
"""

import hashlib
import hmac
import logging
import secrets
import time
from datetime import datetime, timedelta
from typing import Optional, Dict
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)


@dataclass
class SecurityEvent:
    event_type: str  # LOGIN_SUCCESS, LOGIN_FAILURE, PASSWORD_CHANGE, PERMISSION_CHANGE, DATA_EXPORT
    user_id: Optional[str]
    ip_address: str
    details: str
    timestamp: datetime
    severity: str = "INFO"  # INFO, WARNING, CRITICAL


class LoginAttemptTracker:
    """Track failed login attempts for account lockout"""

    def __init__(self, max_attempts: int = 5, lockout_minutes: int = 15):
        self.max_attempts = max_attempts
        self.lockout_minutes = lockout_minutes
        self._attempts: Dict[str, list] = {}
        self._lockouts: Dict[str, datetime] = {}

    def record_failure(self, identifier: str):
        now = datetime.utcnow()
        if identifier not in self._attempts:
            self._attempts[identifier] = []
        self._attempts[identifier].append(now)
        # Clean old attempts
        cutoff = now - timedelta(minutes=self.lockout_minutes)
        self._attempts[identifier] = [t for t in self._attempts[identifier] if t > cutoff]

        if len(self._attempts[identifier]) >= self.max_attempts:
            self._lockouts[identifier] = now + timedelta(minutes=self.lockout_minutes)
            logger.warning(f"Account locked out: {identifier}")

    def record_success(self, identifier: str):
        self._attempts.pop(identifier, None)
        self._lockouts.pop(identifier, None)

    def is_locked(self, identifier: str) -> bool:
        lockout_until = self._lockouts.get(identifier)
        if lockout_until and datetime.utcnow() < lockout_until:
            return True
        if lockout_until:
            self._lockouts.pop(identifier, None)
        return False

    def remaining_attempts(self, identifier: str) -> int:
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=self.lockout_minutes)
        recent = [t for t in self._attempts.get(identifier, []) if t > cutoff]
        return max(0, self.max_attempts - len(recent))


login_tracker = LoginAttemptTracker()


def generate_api_key() -> str:
    """Generate a secure API key"""
    return f"iq_{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage"""
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(api_key: str, hashed: str) -> bool:
    """Verify an API key against its hash"""
    return hmac.compare_digest(hash_api_key(api_key), hashed)


class SessionManager:
    """Manage active user sessions for concurrent session limits"""

    def __init__(self, max_sessions_per_user: int = 5):
        self.max_sessions = max_sessions_per_user
        self._sessions: Dict[str, list] = {}

    def create_session(self, user_id: str, session_id: str) -> bool:
        if user_id not in self._sessions:
            self._sessions[user_id] = []
        # Clean expired sessions (older than 24h)
        now = time.time()
        self._sessions[user_id] = [(s, t) for s, t in self._sessions[user_id] if now - t < 86400]

        if len(self._sessions[user_id]) >= self.max_sessions:
            # Remove oldest session
            self._sessions[user_id].pop(0)

        self._sessions[user_id].append((session_id, now))
        return True

    def invalidate_session(self, user_id: str, session_id: str):
        if user_id in self._sessions:
            self._sessions[user_id] = [(s, t) for s, t in self._sessions[user_id] if s != session_id]

    def invalidate_all(self, user_id: str):
        self._sessions.pop(user_id, None)

    def get_active_count(self, user_id: str) -> int:
        now = time.time()
        if user_id in self._sessions:
            self._sessions[user_id] = [(s, t) for s, t in self._sessions[user_id] if now - t < 86400]
            return len(self._sessions[user_id])
        return 0


session_manager = SessionManager()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add defense-in-depth security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # HSTS when behind TLS-terminating proxy
        if request.headers.get("x-forwarded-proto") == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response
