"""
Patient status endpoints
"""
from fastapi import APIRouter, HTTPException

from app.models.schemas import PatientStatus
from app.core import database

router = APIRouter()


@router.get("/patient-status", response_model=PatientStatus)
async def get_patient_status():
    """
    Get patient status
    
    CURRENT: Returns single patient status (no ID needed)
    """
    status = database.get_patient_status()
    if not status:
        raise HTTPException(status_code=404, detail="No patient status found")
    return status

