"""Users router"""
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.dependencies import get_current_user
from app.models import User
from app.services.users_service import UsersService
from app.schemas.users import UpdateUserRequest

router = APIRouter()


@router.get("/profile")
async def get_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile"""
    return await UsersService.find_by_id(current_user.id)


@router.put("/profile")
async def update_profile(
    update_data: UpdateUserRequest,
    current_user: User = Depends(get_current_user)
):
    """Update current user profile"""
    update_dict = update_data.model_dump(exclude_unset=True)
    return await UsersService.update(current_user.id, update_dict)


@router.get("/{user_id}")
async def get_user_by_id(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get user by ID"""
    return await UsersService.find_by_id(user_id)


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete user by ID"""
    return await UsersService.delete(user_id)

