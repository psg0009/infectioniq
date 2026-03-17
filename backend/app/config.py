"""
InfectionIQ Configuration
Application settings using Pydantic BaseSettings
"""

import secrets
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache


def _generate_dev_secret() -> str:
    """Generate a random secret for development only"""
    return secrets.token_urlsafe(32)


class Settings(BaseSettings):
    """Application settings"""

    # Application
    APP_NAME: str = "InfectionIQ"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Camera health
    CAMERA_STALE_THRESHOLD_SECONDS: int = 60

    # Database
    # Dev: sqlite:///./infectioniq.db
    # Prod: postgresql+asyncpg://user:pass@host:5432/infectioniq
    DATABASE_URL: str = "sqlite:///./infectioniq.db"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # Redis (set to empty to use fakeredis in development)
    REDIS_URL: str = ""
    USE_FAKEREDIS: bool = True

    # Internal service key for CV module and demo simulation (bypasses JWT auth)
    INTERNAL_SERVICE_KEY: str = ""

    # Supabase (primary auth provider)
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""  # From Supabase Dashboard → Settings → API → JWT Secret

    # Security — these MUST be set via environment variables in production
    SECRET_KEY: str = ""
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Password policy
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_DIGIT: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = True

    # HIPAA / PHI Encryption
    PHI_ENCRYPTION_KEY: str = ""  # Fernet key — generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

    # SSO / SAML
    SSO_ENABLED: bool = False
    SSO_ENTITY_ID: str = ""
    SSO_SSO_URL: str = ""
    SSO_SLO_URL: str = ""
    SSO_X509_CERT: str = ""
    SSO_SP_ENTITY_ID: str = "infectioniq-sp"
    SSO_ACS_URL: str = ""

    # FHIR / EMR
    FHIR_ENABLED: bool = True
    FHIR_SERVER_URL: str = ""

    # Consent
    CONSENT_REQUIRED_TYPES: List[str] = ["DATA_COLLECTION", "AI_MONITORING"]
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    # CV Module
    PERSON_CONFIDENCE_THRESHOLD: float = 0.7
    HAND_CONFIDENCE_THRESHOLD: float = 0.5
    SANITIZE_GESTURE_THRESHOLD: float = 0.7
    SANITIZE_MIN_DURATION_SEC: float = 3.0
    SANITIZE_MIN_VOLUME_ML: float = 0.5
    
    # Alerts
    ENABLE_AUDIO_ALERTS: bool = True
    ENABLE_VISUAL_ALERTS: bool = True
    ALERT_COOLDOWN_SECONDS: int = 10

    # Email / SMTP Alerts
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_FROM_EMAIL: str = "alerts@infectioniq.local"
    ALERT_EMAIL_RECIPIENTS: List[str] = []

    # SMS Alerts (webhook-based — works with Twilio, MessageBird, etc.)
    SMS_WEBHOOK_URL: str = ""
    SMS_WEBHOOK_AUTH_TOKEN: str = ""

    # PagerDuty
    PAGERDUTY_ROUTING_KEY: str = ""

    # Generic Webhook
    WEBHOOK_ALERT_URL: str = ""
    WEBHOOK_ALERT_SECRET: str = ""

    # Audit
    AUDIT_RETENTION_DAYS: int = 90

    # Risk Model
    RISK_MODEL_PATH: str = "ml/models/risk_model.onnx"
    
    # Zone risk levels (single source of truth)
    ZONE_RISK_LEVELS: dict = {
        "CRITICAL": 10,
        "STERILE": 7,
        "NON_STERILE": 3,
        "SANITIZER": 0,
        "DOOR": 1
    }

    # Zone Configuration (default - can be overridden per-OR)
    ZONE_CONFIG: dict = {
        "CRITICAL": {
            "polygon": [[0.3, 0.2], [0.7, 0.2], [0.7, 0.5], [0.3, 0.5]]
        },
        "STERILE": {
            "polygon": [[0.15, 0.1], [0.85, 0.1], [0.85, 0.65], [0.15, 0.65]]
        },
        "NON_STERILE": {
            "polygon": [[0.0, 0.65], [1.0, 0.65], [1.0, 1.0], [0.0, 1.0]]
        },
        "SANITIZER": {
            "polygon": [[0.7, 0.85], [0.85, 0.85], [0.85, 1.0], [0.7, 1.0]]
        },
        "DOOR": {
            "polygon": [[0.4, 0.85], [0.6, 0.85], [0.6, 1.0], [0.4, 1.0]]
        }
    }
    
    @field_validator("SECRET_KEY", "JWT_SECRET_KEY", mode="before")
    @classmethod
    def ensure_secret_keys(cls, v: str, info) -> str:
        """Auto-generate secrets in dev, reject empty in production"""
        if v:
            return v
        # Auto-generate for development only
        import os
        env = os.getenv("ENVIRONMENT", "development")
        if env == "production":
            raise ValueError(f"{info.field_name} must be set in production — generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
        return _generate_dev_secret()

    @field_validator("PHI_ENCRYPTION_KEY", mode="before")
    @classmethod
    def ensure_phi_key(cls, v: str) -> str:
        """Auto-generate Fernet key in dev, reject empty in production"""
        if v:
            return v
        import os
        env = os.getenv("ENVIRONMENT", "development")
        if env == "production":
            raise ValueError(
                "PHI_ENCRYPTION_KEY must be set in production — "
                'generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )
        try:
            from cryptography.fernet import Fernet
            return Fernet.generate_key().decode()
        except ImportError:
            return _generate_dev_secret()

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def check_database_url(cls, v: str) -> str:
        """Reject SQLite in production"""
        import os
        env = os.getenv("ENVIRONMENT", "development")
        if env == "production" and "sqlite" in v.lower():
            raise ValueError("SQLite is not supported in production — use PostgreSQL (postgresql+asyncpg://...)")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True


def validate_production_config(s: "Settings") -> List[str]:
    """Check production settings and return list of warnings.

    Call during startup — in production, critical issues should block startup.
    """
    warnings: List[str] = []

    if s.ENVIRONMENT == "production":
        if len(s.SECRET_KEY) < 32:
            warnings.append("SECRET_KEY is shorter than 32 characters")
        if len(s.JWT_SECRET_KEY) < 32:
            warnings.append("JWT_SECRET_KEY is shorter than 32 characters")
        if s.DEBUG:
            warnings.append("DEBUG=True in production")
        if "*" in s.CORS_ORIGINS or "http://localhost:3000" in s.CORS_ORIGINS:
            warnings.append("CORS_ORIGINS contains wildcard or localhost")
        if s.SSO_ENABLED and not s.SSO_X509_CERT:
            warnings.append("SSO is enabled but SSO_X509_CERT is empty")

    return warnings


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
