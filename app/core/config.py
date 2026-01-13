"""
Basic configuration

- CORS origins for development and production
- Supports environment variables for production domains
"""
import os

# Default localhost origins for development
DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8081",
    "http://localhost:19006",
    "https://kare-tau.vercel.app"
]

# Get additional CORS origins from environment variable
ADDITIONAL_CORS_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else []

# Filter out empty strings from split
ADDITIONAL_CORS_ORIGINS = [origin.strip() for origin in ADDITIONAL_CORS_ORIGINS if origin.strip()]

# Combine default and additional origins
CORS_ORIGINS = DEFAULT_CORS_ORIGINS + ADDITIONAL_CORS_ORIGINS