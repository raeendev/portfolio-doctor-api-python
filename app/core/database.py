"""Database connection using SQLAlchemy"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager
from typing import Generator

from config import settings
from app.models import Base

# SQLite database URL
if settings.database_url.startswith("file:"):
    db_path = settings.database_url.replace("file:", "").replace("./", "")
    database_url = f"sqlite:///{db_path}"
else:
    database_url = settings.database_url

# Create engine with SQLite-specific settings
engine = create_engine(
    database_url,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False
)

# Create session factory
# expire_on_commit=False prevents detached instance errors when accessing attributes after commit
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


def init_database():
    """Initialize database - create all tables"""
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully")


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Get database session context manager"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_dependency() -> Generator[Session, None, None]:
    """FastAPI dependency for database session"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def connect_database():
    """Connect to database"""
    init_database()
    print("Database connected successfully")


async def disconnect_database():
    """Disconnect from database"""
    engine.dispose()
    print("Database disconnected")


# Legacy prisma compatibility (will return None, but won't break imports)
class MockPrisma:
    """Mock Prisma client for compatibility"""
    pass


prisma = None  # No longer used, using SQLAlchemy instead
PRISMA_AVAILABLE = False

__all__ = ["get_db", "get_db_dependency", "connect_database", "disconnect_database", "SessionLocal", "engine", "prisma"]
