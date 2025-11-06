"""Main FastAPI application"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.middleware.api_logger import ApiLoggerMiddleware

from config import settings
from app.core.database import connect_database, disconnect_database
from app.core.admin_seed import seed_default_admin
from app.routers import auth, portfolio, exchanges, users, health, admin, user_api, profiling, trading_plan


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    print("Portfolio Doctor API (Python) is starting...")
    await connect_database()
    # Seed default admin if not exists
    try:
        seed_default_admin()
        print("Default admin ensured (use env ADMIN_EMAIL/ADMIN_USERNAME/ADMIN_PASSWORD to override)")
    except Exception as e:
        print(f"Admin seed failed: {e}")
    yield
    # Shutdown
    await disconnect_database()
    print("Portfolio Doctor API is shutting down...")


app = FastAPI(
    title="Portfolio Doctor API",
    description="Cryptocurrency Portfolio Management System API",
    version="1.0.0",
    lifespan=lifespan,
)

# API Logger Middleware
app.add_middleware(ApiLoggerMiddleware)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin,
    allow_credentials=settings.cors_credentials,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_allowed_headers,
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["Portfolio"])
app.include_router(exchanges.router, prefix="/api/exchanges", tags=["Exchanges"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(health.router, prefix="/api/health", tags=["Health"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin API"])
app.include_router(user_api.router, prefix="/api/user", tags=["User API"])
app.include_router(profiling.router, prefix="/api/profiling", tags=["Profiling"])
app.include_router(trading_plan.router, prefix="/api/trading-plan", tags=["Trading Plan"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Portfolio Doctor API (Python)",
        "version": "1.0.0",
        "docs": "/api/docs" if settings.enable_swagger else None,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=True,
    )
