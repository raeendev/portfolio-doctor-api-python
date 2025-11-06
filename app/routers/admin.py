"""Admin API router"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.dependencies import get_current_user
from app.core.admin_auth import get_admin_user
from app.core.database import get_db
from app.models import User, Portfolio, ExchangeAPIKey
from app.services.admin_service import AdminService

router = APIRouter()


@router.get("/stats")
async def get_system_stats(admin_user: User = Depends(get_admin_user)):
    """Get system statistics"""
    return await AdminService.get_system_stats()


@router.get("/health")
async def get_system_health(admin_user: User = Depends(get_admin_user)):
    """Get system health status"""
    return await AdminService.get_system_health()


@router.get("/users")
async def get_all_users(admin_user: User = Depends(get_admin_user)):
    """Get all users"""
    return await AdminService.get_all_users()


@router.get("/users/{user_id}")
async def get_user_by_id(
    user_id: str,
    admin_user: User = Depends(get_admin_user)
):
    """Get user by ID"""
    return await AdminService.get_user_by_id(user_id)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    admin_user: User = Depends(get_admin_user)
):
    """Delete user by ID"""
    return await AdminService.delete_user(user_id)

