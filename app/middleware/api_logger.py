"""API Logger Middleware"""
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import logging

logger = logging.getLogger("API")


class ApiLoggerMiddleware(BaseHTTPMiddleware):
    """Log all API requests and responses"""
    
    async def dispatch(self, request: Request, call_next):
        """Process request and log"""
        method = request.method
        url = str(request.url)
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent", "")
        
        # Log request
        logger.info(f"{method} {url} - {client_ip} - {user_agent}")
        
        # Process request
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Log response
        status_code = response.status_code
        content_length = response.headers.get("content-length", "0")
        
        logger.info(
            f"{method} {url} {status_code} {content_length}b - {client_ip} - {process_time:.3f}s"
        )
        
        return response

