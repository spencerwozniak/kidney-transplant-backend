"""
Patient management endpoints
"""
from fastapi import APIRouter, HTTPException, Request
import uuid

from app.database.schemas import Patient
from app.database import storage as database
from app.services.checklist.initialization import create_default_checklist
from app.services.utils import convert_checklist_datetimes
from app.api.utils import get_device_id

router = APIRouter()


@router.post("/patients", response_model=Patient)
async def create_patient(patient: Patient, request: Request):
    """
    Save patient (intake form)
    
    Creates a patient for the device making the request.
    Automatically creates default checklist for new patient.
    
    Returns the created patient with its ID, which should be used for subsequent requests.
    """
    device_id = get_device_id(request)
    patient.id = str(uuid.uuid4())
    
    # Save patient bound to device_id
    database.save_patient(patient.model_dump(), device_id)
    
    # Create default checklist for new patient
    checklist = create_default_checklist(patient.id)
    checklist.id = str(uuid.uuid4())
    
    # Prepare checklist data for storage
    checklist_data = convert_checklist_datetimes(checklist.model_dump())
    
    # Save checklist bound to same device_id
    database.save_checklist(checklist_data, device_id)
    
    # Precompute and save initial patient status (avoids computation on first GET /patient-status)
    from app.services.status.computation import create_initial_status
    from app.services.utils import convert_datetime_to_iso
    initial_status = create_initial_status(patient.id, device_id)
    initial_status.id = str(uuid.uuid4())
    status_data = convert_datetime_to_iso(initial_status.model_dump(), ['updated_at'])
    database.save_patient_status(status_data, device_id)
    
    # Return patient (frontend should use this response directly)
    return patient


@router.get("/patients", response_model=Patient)
async def get_patient(request: Request):
    """
    Get patient for the device making the request
    
    Requires X-Device-ID header matching the device_id used when creating the patient.
    If no patient is found, returns 404. This usually means:
    - No patient was created for this device_id yet, OR
    - The X-Device-ID header is missing/incorrect
    """
    device_id = get_device_id(request)
    patient = database.get_patient(device_id)
    if not patient:
        raise HTTPException(
            status_code=404, 
            detail=f"No patient found for device_id. Make sure you're sending the same X-Device-ID header used when creating the patient."
        )
    return patient


@router.delete("/patients")
async def delete_patient(request: Request):
    """
    Delete patient and associated data for the device making the request
    Returns 404 if no patient exists to ensure DELETE never silently fails
    """
    device_id = get_device_id(request)
    # Check if patient exists before deletion
    patient = database.get_patient(device_id)
    if not patient:
        raise HTTPException(status_code=404, detail="No patient found")
    
    # Delete patient and all associated data
    database.delete_patient(device_id)
    return {"message": "Patient deleted successfully"}

