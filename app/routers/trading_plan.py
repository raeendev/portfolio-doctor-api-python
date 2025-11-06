"""Trading plan router"""
from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.models import User
from app.services.trading_plan_service import TradingPlanService

router = APIRouter()


@router.get("/")
async def get_trading_plan(current_user: User = Depends(get_current_user)):
    """Get user trading plan"""
    return await TradingPlanService.get_trading_plan(current_user.id)

