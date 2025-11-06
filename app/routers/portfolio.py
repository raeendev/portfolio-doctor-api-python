"""Portfolio router"""
from fastapi import APIRouter, Depends, HTTPException
from app.core.dependencies import get_current_user
from app.services.portfolio_service import PortfolioService

router = APIRouter()
portfolio_service = PortfolioService()


@router.get("/")
async def get_portfolio(current_user=Depends(get_current_user)):
    """Get user portfolio"""
    try:
        # Access user.id while session is still active
        user_id = current_user.id
        return await portfolio_service.get_portfolio(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync")
async def sync_portfolio(current_user=Depends(get_current_user)):
    """Sync portfolio from exchanges"""
    try:
        # Access user.id while session is still active
        user_id = current_user.id
        return await portfolio_service.sync_portfolio(user_id)
    except Exception as e:
        raise HTTPException(status_code=404 if "No connected exchanges" in str(e) else 500, detail=str(e))

