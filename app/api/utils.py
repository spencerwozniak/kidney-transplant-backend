"""
Utility functions for API endpoints
"""
from fastapi import Request, HTTPException


def get_device_id(request: Request) -> str:
    """
    Extract device ID from request headers
    
    Raises HTTPException with 400 status if device ID is missing (not 404)
    Includes device_id in error message for debugging
    """
    device_id = request.headers.get('X-Device-ID')
    if not device_id:
        raise HTTPException(
            status_code=400,
            detail="Missing X-Device-ID header. This header is required for all requests."
        )
    return device_id

