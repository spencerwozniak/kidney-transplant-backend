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
    
    Returns cached status if available (computed after patient/questionnaire updates).
    Only recomputes if no cached status exists.
    """
    device_id = get_device_id(request)
    
    # Check for cached status first (avoids recomputation on every request)
    cached_status = database.get_patient_status(device_id)
    if cached_status:
        # Return cached status immediately (fast path)
        return PatientStatus(**cached_status)
    
    # Cache miss - need to compute status
    # Get current patient
    patient = database.get_patient(device_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    patient_id = patient.get('id')
    
    # Compute status from all questionnaires (or create initial status if no questionnaires exist)
    try:
        status = compute_patient_status_from_all_questionnaires(patient_id, device_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    # Preserve existing status ID if it exists (don't regenerate on recomputation)
    # Only generate new ID if this is the first time creating a status
    import uuid
    existing_status = database.get_patient_status(device_id)
    if existing_status and existing_status.get('id'):
        # Preserve the existing ID
        status.id = existing_status['id']
    elif not status.id:
        # Only generate new ID if no existing status exists
        status.id = str(uuid.uuid4())
    
    # Save computed status (this also updates the cache)
    status_data = convert_datetime_to_iso(status.model_dump(), ['updated_at'])
    database.save_patient_status(status_data, device_id)
    
    return status

