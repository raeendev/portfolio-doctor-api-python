"""User API router"""
from fastapi import APIRouter, Depends
from datetime import datetime

from app.core.dependencies import get_current_user
from app.models import User

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(current_user: User = Depends(get_current_user)):
    """Get user dashboard data"""
    return {
        "message": "User dashboard data",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }


@router.get("/profile")
async def get_profile(current_user: User = Depends(get_current_user)):
    """Get user profile"""
    return {
        "message": "User profile data",
        "timestamp": datetime.utcnow().isoformat(),
    }

