"""Authentication schemas"""
from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    """User registration request"""
    email: EmailStr
    username: str
    password: str
    
    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if len(v) < 3 or len(v) > 20:
            raise ValueError("Username must be between 3 and 20 characters")
        if not v.replace("_", "").isalnum():
            raise ValueError("Username must contain only letters, numbers, and underscores")
        return v
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        # Bcrypt has a 72-byte limit, warn if password is too long
        password_bytes = v.encode('utf-8')
        if len(password_bytes) > 72:
            raise ValueError("Password is too long. Maximum 72 bytes (approximately 72 characters for ASCII, less for Unicode)")
        return v


class LoginRequest(BaseModel):
    """User login request"""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """User response model"""
    id: str
    email: str
    username: str
    role: str
    createdAt: str
    
    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    """Authentication response"""
    user: UserResponse
    accessToken: str

