"""
Audit logging for HIPAA compliance
"""

import logging
from datetime import datetime
from typing import Optional, Any, Dict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.database import async_session_maker
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)

STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


async def log_audit(
    user_id: Optional[str],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    """Log an audit event to the database"""
    try:
        async with async_session_maker() as session:
            entry = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent,
                timestamp=datetime.utcnow(),
            )
            session.add(entry)
            await session.commit()
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware that logs state-changing API requests"""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        if request.method in STATE_CHANGING_METHODS and response.status_code < 400:
            # Extract user_id from request state (set by auth dependency)
            user_id = getattr(request.state, "user_id", None)
            path = request.url.path
            # Derive resource type from path
            parts = [p for p in path.strip("/").split("/") if p]
            resource_type = parts[2] if len(parts) > 2 else "unknown"
            resource_id = parts[3] if len(parts) > 3 else None

            await log_audit(
                user_id=str(user_id) if user_id else None,
                action=request.method,
                resource_type=resource_type,
                resource_id=resource_id,
                details={"path": path, "status": response.status_code},
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent", "")[:500],
            )

        return response
