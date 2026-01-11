"""
Patient status endpoints
"""
from fastapi import APIRouter, HTTPException

from app.models.schemas import PatientStatus
from app.core import database
from app.services.status_computation import recompute_pathway_stage
from app.services.utils import convert_datetime_to_iso

router = APIRouter()


@router.get("/patient-status", response_model=PatientStatus)
async def get_patient_status():
    """
    Get patient status
    
    CURRENT: Returns single patient status (no ID needed)
    Recomputes pathway stage based on current checklist state
    """
    status_data = database.get_patient_status()
    if not status_data:
        raise HTTPException(status_code=404, detail="No patient status found")
    
    # Convert dict to PatientStatus model
    status = PatientStatus(**status_data)
    
    # Recompute pathway stage (checklist may have changed)
    status = recompute_pathway_stage(status)
    
    # Save updated status with new pathway stage
    status_data_updated = convert_datetime_to_iso(status.model_dump(), ['updated_at'])
    database.save_patient_status(status_data_updated)
    
    return status

