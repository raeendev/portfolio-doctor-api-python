"""Admin authentication dependency"""
from fastapi import HTTPException, status, Depends
from app.core.dependencies import get_current_user
from app.models import User


async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Verify user is admin"""
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

