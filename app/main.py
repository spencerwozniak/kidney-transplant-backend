"""
FastAPI app

- Minimal setup for MVP
- CORS configured for mobile app development
- Single router for all endpoints
- Basic health check
"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables from .env file early
try:
    from dotenv import load_dotenv
    # Get the project root directory (parent of app/)
    project_root = Path(__file__).parent.parent
    env_path = project_root / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    # python-dotenv not installed, skip loading .env
    pass

from app.api import router
from app.core.config import CORS_ORIGINS
from app.api.middleware import TimingMiddleware

app = FastAPI()

# Add timing middleware for performance monitoring
# Logs request duration and device_id for all requests
app.add_middleware(TimingMiddleware)

# CORS middleware configuration
# For development/demo: allow all origins. For production, restrict to your app origins.
# Explicitly allow X-Device-ID header for device-based authentication
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,  # Uses CORS_ORIGINS from config (env var)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, PUT, DELETE, OPTIONS, etc.)
    allow_headers=["*"],  # Allow all headers including X-Device-ID, Content-Type, etc.
    expose_headers=["*"],  # Expose all headers to the client
)

app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    """
    Basic health check
    """
    return {"status": "ok"}

