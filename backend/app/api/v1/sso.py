"""
SSO/SAML API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import urlencode

from app.core.database import get_db
from app.core.saml import get_sso_config, create_authn_request, parse_saml_response, generate_sp_metadata
from app.core.security import create_access_token, create_refresh_token
from app.core.enums import UserRole
from app.models.user import User
from app.config import settings

router = APIRouter()


@router.get("/login")
async def sso_login():
    """Redirect to IdP for SAML authentication"""
    config = get_sso_config()
    if config is None:
        raise HTTPException(status_code=400, detail="SSO is not enabled")

    saml_request = create_authn_request(config)
    params = urlencode({"SAMLRequest": saml_request})
    return RedirectResponse(url=f"{config.sso_url}?{params}")


@router.post("/acs")
async def assertion_consumer_service(
    SAMLResponse: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Receive SAML response from IdP, create/login user, return JWT"""
    config = get_sso_config()
    if config is None:
        raise HTTPException(status_code=400, detail="SSO is not enabled")

    attributes = parse_saml_response(SAMLResponse)
    if attributes is None:
        raise HTTPException(status_code=401, detail="Invalid SAML response")

    email = attributes.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="No email in SAML response")

    # Find or create user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        from app.core.security import hash_password
        import uuid as _uuid
        user = User(
            email=email,
            password_hash=hash_password(_uuid.uuid4().hex),  # random password (SSO users don't use passwords)
            full_name=attributes.get("displayName", attributes.get("name", email.split("@")[0])),
            role=UserRole.VIEWER,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    token_data = {"sub": str(user.id), "role": user.role.value}
    access = create_access_token(token_data)
    refresh = create_refresh_token(token_data)

    # Redirect to frontend with tokens in URL fragment
    frontend_url = settings.CORS_ORIGINS[0] if settings.CORS_ORIGINS else "http://localhost:3000"
    return RedirectResponse(url=f"{frontend_url}/sso-callback#access_token={access}&refresh_token={refresh}")


@router.get("/metadata")
async def sp_metadata():
    """Return SP metadata XML"""
    config = get_sso_config()
    if config is None:
        raise HTTPException(status_code=400, detail="SSO is not enabled")
    return Response(content=generate_sp_metadata(config), media_type="application/xml")


@router.get("/logout")
async def sso_logout():
    """Initiate single logout"""
    config = get_sso_config()
    if config is None:
        raise HTTPException(status_code=400, detail="SSO is not enabled")
    if config.slo_url:
        return RedirectResponse(url=config.slo_url)
    return {"status": "logged_out"}
