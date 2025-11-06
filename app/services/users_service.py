"""Users service"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User


class UsersService:
    """User management business logic"""
    
    @staticmethod
    async def find_by_id(user_id: str):
        """Find user by ID"""
        with get_db() as db:
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            return {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "createdAt": user.createdAt.isoformat(),
                "updatedAt": user.updatedAt.isoformat(),
            }
    
    @staticmethod
    async def update(user_id: str, update_data: dict):
        """Update user"""
        with get_db() as db:
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # Update fields
            if "email" in update_data:
                user.email = update_data["email"]
            if "username" in update_data:
                user.username = update_data["username"]
            
            db.flush()
            
            return {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "createdAt": user.createdAt.isoformat(),
                "updatedAt": user.updatedAt.isoformat(),
            }
    
    @staticmethod
    async def delete(user_id: str):
        """Delete user"""
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

