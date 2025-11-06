"""Authentication service"""
from datetime import timedelta
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
import uuid

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.schemas.auth import RegisterRequest, LoginRequest, AuthResponse, UserResponse
from app.models import User


class AuthService:
    """Authentication business logic"""
    
    @staticmethod
    async def register(data: RegisterRequest) -> AuthResponse:
        """Register a new user"""
        with get_db() as db:
            # Check if user already exists
            existing_user = db.query(User).filter(
                or_(User.email == data.email, User.username == data.username)
            ).first()
            
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User with this email or username already exists"
                )
            
            # Hash password
            hashed_password = get_password_hash(data.password)
            
            # Create user
            user = User(
                id=str(uuid.uuid4()),
                email=data.email,
                username=data.username,
                password=hashed_password,
                role="USER",
            )
            db.add(user)
            db.flush()  # Get the ID
            
            # Generate JWT token
            access_token = create_access_token(
                data={"sub": user.id, "email": user.email}
            )
            
            return AuthResponse(
                user=UserResponse(
                    id=user.id,
                    email=user.email,
                    username=user.username,
                    role=user.role,
                    createdAt=user.createdAt.isoformat(),
                ),
                accessToken=access_token,
            )
    
    @staticmethod
    async def login(data: LoginRequest) -> AuthResponse:
        """Login user"""
        with get_db() as db:
            # Find user
            user = db.query(User).filter(User.email == data.email).first()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials"
                )
            
            # Verify password
            if not verify_password(data.password, user.password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials"
                )
            
            # Generate JWT token
            access_token = create_access_token(
                data={"sub": user.id, "email": user.email}
            )
            
            return AuthResponse(
                user=UserResponse(
                    id=user.id,
                    email=user.email,
                    username=user.username,
                    role=user.role,
                    createdAt=user.createdAt.isoformat(),
                ),
                accessToken=access_token,
            )
    
    @staticmethod
    async def validate_user(user_id: str):
        """Validate user exists and is active"""
        with get_db() as db:
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found"
                )
            
            if not user.isActive:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User account is inactive"
                )
            
            return {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "role": user.role,
                "isActive": user.isActive,
                "createdAt": user.createdAt,
            }
