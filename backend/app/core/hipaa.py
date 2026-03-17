"""
HIPAA compliance utilities - PHI encryption, masking
"""

import logging
from typing import Optional
from cryptography.fernet import Fernet

from app.config import settings

logger = logging.getLogger(__name__)

_fernet: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = settings.PHI_ENCRYPTION_KEY
        if not key:
            if settings.ENVIRONMENT == "production":
                raise RuntimeError(
                    "PHI_ENCRYPTION_KEY must be set in production. "
                    "Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
                )
            key = Fernet.generate_key().decode()
            logger.warning("PHI_ENCRYPTION_KEY not set - generated ephemeral key (data will be lost on restart)")
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_phi(data: str) -> str:
    """Encrypt PHI data using AES-256 (Fernet)"""
    if not data:
        return data
    return _get_fernet().encrypt(data.encode()).decode()


def decrypt_phi(encrypted_data: str) -> str:
    """Decrypt PHI data"""
    if not encrypted_data:
        return encrypted_data
    return _get_fernet().decrypt(encrypted_data.encode()).decode()


def mask_phi(data: str) -> str:
    """Mask PHI for logging - shows only last 4 characters"""
    if not data or len(data) <= 4:
        return "****"
    return "*" * (len(data) - 4) + data[-4:]
