"""
Patient status endpoints
"""
from fastapi import APIRouter, HTTPException, Request

from app.database.schemas import PatientStatus
from app.database import storage as database
from app.services.status.computation import compute_patient_status_from_all_questionnaires
from app.services.utils import convert_datetime_to_iso
from app.api.utils import get_device_id

router = APIRouter()


@router.get("/patient-status", response_model=PatientStatus)
async def get_patient_status(request: Request):
    """
    Get patient status
    
    Computes status by rolling up all questionnaires for the device's patient
    """
    device_id = get_device_id(request)
    # Get current patient
    patient = database.get_patient(device_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    patient_id = patient.get('id')
    
    # Compute status from all questionnaires (or create initial status if no questionnaires exist)
    status = compute_patient_status_from_all_questionnaires(patient_id, device_id)
    
    # Generate ID if not set
    import uuid
    if not status.id:
        status.id = str(uuid.uuid4())
    
    # Save computed status
    status_data = convert_datetime_to_iso(status.model_dump(), ['updated_at'])
    database.save_patient_status(status_data, device_id)
    
    return status

