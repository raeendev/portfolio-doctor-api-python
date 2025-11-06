"""Admin user seeding on startup"""
import os
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models import User


def seed_default_admin(
    email: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> None:
    """Create a default admin user if none exists.
    Values can be provided via env vars ADMIN_EMAIL, ADMIN_USERNAME, ADMIN_PASSWORD.
    Defaults: admin@example.com / admin / Admin@12345
    """
    admin_email = email or os.getenv("ADMIN_EMAIL", "admin@example.com").strip()
    admin_username = username or os.getenv("ADMIN_USERNAME", "admin").strip()
    admin_password = password or os.getenv("ADMIN_PASSWORD", "Admin@12345")

    db: Session = SessionLocal()
    try:
        # If any ADMIN user exists, skip
        existing_admin = db.query(User).filter(User.role == "ADMIN").first()
        if existing_admin:
            return

        # If not, check by email/username
        existing_user = db.query(User).filter(
            (User.email == admin_email) | (User.username == admin_username)
        ).first()
        if existing_user:
            # Promote to ADMIN if needed
            if existing_user.role != "ADMIN":
                existing_user.role = "ADMIN"
                db.flush()
                db.commit()
            return

        # Create new admin user
        hashed_password = get_password_hash(admin_password)
        admin = User(
            id=str(uuid.uuid4()),
            email=admin_email,
            username=admin_username,
            password=hashed_password,
            role="ADMIN",
            isActive=True,
        )
        db.add(admin)
        db.flush()
        db.commit()
    finally:
        db.close()


