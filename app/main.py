"""
FastAPI app

- Minimal setup for MVP
- CORS configured for mobile app development
- Single router for all endpoints
- Basic health check
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

