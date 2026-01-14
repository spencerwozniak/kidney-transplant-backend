"""
Request timing and logging middleware
"""
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class TimingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log request timing and device_id for performance monitoring
    """
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        device_id = request.headers.get('X-Device-ID', 'missing')
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log timing info
        print(f"[TIMING] {request.method} {request.url.path} | device_id={device_id} | duration={duration_ms:.2f}ms | status={response.status_code}")
        
        return response
