"""User schemas"""
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional


class UpdateUserRequest(BaseModel):
    """Update user request"""
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    
    @field_validator("username")
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if len(v) < 3 or len(v) > 20:
            raise ValueError("Username must be between 3 and 20 characters")
        if not v.replace("_", "").isalnum():
            raise ValueError("Username must contain only letters, numbers, and underscores")
        return v

