"""Trading plan service"""
from app.core.database import get_db


class TradingPlanService:
    """Trading plan business logic"""
    
    @staticmethod
    async def get_trading_plan(user_id: str):
        """Get trading plan for user"""
        # TODO: Implement trading plan management
        return {"message": "Trading plan management not implemented yet"}

