"""Authentication router"""
from fastapi import APIRouter, Depends
from app.services.auth_service import AuthService
from app.schemas.auth import RegisterRequest, LoginRequest, AuthResponse, UserResponse
from app.core.dependencies import get_current_user

router = APIRouter()


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(data: RegisterRequest):
    """Register a new user"""
    return await AuthService.register(data)


@router.post("/login", response_model=AuthResponse)
async def login(data: LoginRequest):
    """Login user"""
    return await AuthService.login(data)


@router.get("/profile", response_model=UserResponse)
async def get_profile(current_user=Depends(get_current_user)):
    """Get current user profile"""
    # Access role as string (not enum)
    role_value = current_user.role if isinstance(current_user.role, str) else str(current_user.role)
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        role=role_value,
        createdAt=current_user.createdAt.isoformat(),
    )

