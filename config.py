"""Application configuration"""
import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # Server
    port: int = int(os.getenv("PORT", "3001"))
    cors_origin_str: str = os.getenv("CORS_ORIGIN", "http://localhost:3000,http://127.0.0.1:3000")
    
    @property
    def cors_origin(self) -> List[str]:
        """Parse CORS origin from string"""
        if isinstance(self.cors_origin_str, str):
            return [origin.strip() for origin in self.cors_origin_str.split(",") if origin.strip()]
        return ["http://localhost:3000"]
    
    cors_credentials: bool = True
    cors_methods: List[str] = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    cors_allowed_headers: List[str] = ["Content-Type", "Authorization", "Accept", "X-Requested-With"]
    
    # JWT
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me-in-env")
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    # Database  
    database_url: str = "file:./dev.db"
    
    # Features
    enable_swagger: bool = os.getenv("ENABLE_SWAGGER", "true").lower() == "true"
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore"
    }


settings = Settings()

