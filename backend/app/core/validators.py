"""
Request Validation Utilities
Common validation patterns for API endpoints
"""

import re
from typing import Optional
from fastapi import HTTPException
from pydantic import BaseModel, field_validator, EmailStr


class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = 20

    @field_validator("page")
    @classmethod
    def page_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("page must be >= 1")
        return v

    @field_validator("page_size")
    @classmethod
    def page_size_limits(cls, v: int) -> int:
        if v < 1 or v > 100:
            raise ValueError("page_size must be between 1 and 100")
        return v

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def validate_uuid(value: str, field_name: str = "id") -> str:
    """Validate UUID format"""
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
    )
    if not uuid_pattern.match(value):
        raise HTTPException(status_code=422, detail=f"Invalid UUID format for {field_name}")
    return value


def validate_or_number(or_number: str) -> str:
    """Validate OR number format"""
    if not re.match(r"^OR-\d{1,3}$", or_number):
        raise HTTPException(status_code=422, detail="OR number must be in format OR-1 through OR-999")
    return or_number


def sanitize_string(value: str, max_length: int = 500) -> str:
    """Sanitize user input string"""
    value = value.strip()
    if len(value) > max_length:
        value = value[:max_length]
    # Remove control characters
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", value)
    return value
