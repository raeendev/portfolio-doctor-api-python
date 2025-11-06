"""Profiling router"""
from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.models import User
from app.services.profiling_service import ProfilingService

router = APIRouter()


@router.get("/questionnaire")
async def get_questionnaire(current_user: User = Depends(get_current_user)):
    """Get risk profiling questionnaire"""
    return await ProfilingService.get_questionnaire()

