"""
InfectionIQ Configuration
Application settings using Pydantic BaseSettings
"""

from typing import List
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    APP_NAME: str = "InfectionIQ"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    
    # Database (SQLite for development)
    DATABASE_URL: str = "sqlite:///./infectioniq.db"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # Redis (set to empty to use fakeredis)
    REDIS_URL: str = ""
    USE_FAKEREDIS: bool = True
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_SECRET_KEY: str = "your-jwt-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
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
    
    # Risk Model
    RISK_MODEL_PATH: str = "ml/models/risk_model.onnx"
    
    # Zone Configuration (default - can be overridden per-OR)
    ZONE_CONFIG: dict = {
        "CRITICAL": {
            "polygon": [[0.3, 0.2], [0.7, 0.2], [0.7, 0.5], [0.3, 0.5]],
            "risk_level": 10
        },
        "STERILE": {
            "polygon": [[0.15, 0.1], [0.85, 0.1], [0.85, 0.65], [0.15, 0.65]],
            "risk_level": 7
        },
        "NON_STERILE": {
            "polygon": [[0.0, 0.65], [1.0, 0.65], [1.0, 1.0], [0.0, 1.0]],
            "risk_level": 3
        },
        "SANITIZER": {
            "polygon": [[0.7, 0.85], [0.85, 0.85], [0.85, 1.0], [0.7, 1.0]],
            "is_sanitizer": True
        },
        "DOOR": {
            "polygon": [[0.4, 0.85], [0.6, 0.85], [0.6, 1.0], [0.4, 1.0]],
            "is_entry_exit": True
        }
    }
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
