"""
Utility functions for API endpoints
"""
from fastapi import Request, HTTPException


def get_device_id(request: Request) -> str:
    """
    Extract device ID from request headers
    
    Raises HTTPException if device ID is missing
    """
    device_id = request.headers.get('X-Device-ID')
    if not device_id:
        raise HTTPException(
            status_code=400,
            detail="X-Device-ID header is required"
        )
    return device_id

