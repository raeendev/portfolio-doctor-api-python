"""Admin service"""
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User, Portfolio, ExchangeAPIKey


class AdminService:
    """Admin business logic"""
    
    @staticmethod
    async def get_system_stats():
        """Get system statistics"""
        with get_db() as db:
            user_count = db.query(User).count()
            portfolio_count = db.query(Portfolio).count()
            
            # Count trades - for now return 0 as Trade model might not exist
            trade_count = 0
            
            return {
                "users": user_count,
                "portfolios": portfolio_count,
                "trades": trade_count,
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    @staticmethod
    async def get_all_users():
        """Get all users"""
        with get_db() as db:
            users = db.query(User).order_by(User.createdAt.desc()).all()
            return [
                {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "createdAt": user.createdAt.isoformat(),
                    "updatedAt": user.updatedAt.isoformat(),
                }
                for user in users
            ]
    
    @staticmethod
    async def get_user_by_id(user_id: str):
        """Get user by ID"""
        with get_db() as db:
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # Get related data
            portfolio = db.query(Portfolio).filter(Portfolio.userId == user_id).first()
            exchange_keys = db.query(ExchangeAPIKey).filter(ExchangeAPIKey.userId == user_id).all()
            
            return {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "createdAt": user.createdAt.isoformat(),
                "updatedAt": user.updatedAt.isoformat(),
                "portfolio": {
                    "id": portfolio.id,
                    "totalValueUSD": portfolio.totalValueUSD,
                } if portfolio else None,
                "exchangeKeys": [
                    {
                        "id": key.id,
                        "exchange": key.exchange,
                        "isActive": key.isActive,
                    }
                    for key in exchange_keys
                ],
            }
    
    @staticmethod
    async def delete_user(user_id: str):
        """Delete user by ID"""
        with get_db() as db:
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            db.delete(user)
            db.flush()
            
            return {"message": "User deleted successfully"}
    
    @staticmethod
    async def get_system_health():
        """Get system health status"""
        try:
            with get_db() as db:
                # Test database connection
                db.execute("SELECT 1")
                return {
                    "status": "healthy",
                    "database": "connected",
                    "timestamp": datetime.utcnow().isoformat(),
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

