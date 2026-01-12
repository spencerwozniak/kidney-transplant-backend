"""
Patient status endpoints
"""
from fastapi import APIRouter, HTTPException
import uuid

from app.models.schemas import PatientStatus
from app.core import database
from app.services.status_computation import recompute_pathway_stage, create_initial_status
from app.services.utils import convert_datetime_to_iso

router = APIRouter()


@router.get("/patient-status", response_model=PatientStatus)
async def get_patient_status():
    """
    Get patient status
    
    CURRENT: Returns single patient status (no ID needed)
    If no status exists, creates an initial status based on patient data.
    Recomputes pathway stage based on current checklist state
    """
    status_data = database.get_patient_status()
    
    if not status_data:
        # No status exists yet - create initial status
        patient = database.get_patient()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        # Create initial status based on patient data (e.g., has_referral)
        status = create_initial_status(patient.get('id'))
        status.id = str(uuid.uuid4())
        
        # Save initial status
        status_data = convert_datetime_to_iso(status.model_dump(), ['updated_at'])
        database.save_patient_status(status_data)
        
        return status
    
    # Convert dict to PatientStatus model
    status = PatientStatus(**status_data)
    
    # Recompute pathway stage (checklist may have changed)
    status = recompute_pathway_stage(status)
    
    # Save updated status with new pathway stage
    status_data_updated = convert_datetime_to_iso(status.model_dump(), ['updated_at'])
    database.save_patient_status(status_data_updated)
    
    return status

