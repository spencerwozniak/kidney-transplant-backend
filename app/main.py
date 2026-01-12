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

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    """
    Basic health check
    """
    return {"status": "ok"}

