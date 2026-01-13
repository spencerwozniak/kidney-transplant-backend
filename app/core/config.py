"""
Basic configuration

- CORS origins loaded from environment variables
- Format: Comma-separated list of origins
"""
import os

# Get CORS origins from environment variable
CORS_ORIGINS_STR = os.getenv("CORS_ORIGINS", "")

if not CORS_ORIGINS_STR:
    raise ValueError(
        "CORS_ORIGINS environment variable is required. "
        "Set it to a comma-separated list of allowed origins."
    )

# Split by comma and clean up whitespace
CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_STR.split(",") if origin.strip()]

if not CORS_ORIGINS:
    raise ValueError("CORS_ORIGINS environment variable is set but contains no valid origins")