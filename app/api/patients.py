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
    Automatically creates default checklist for new patient
    """
    device_id = get_device_id(request)
    patient.id = str(uuid.uuid4())
    database.save_patient(patient.model_dump(), device_id)
    
    # Create default checklist for new patient
    checklist = create_default_checklist(patient.id)
    checklist.id = str(uuid.uuid4())
    
    # Prepare checklist data for storage
    checklist_data = convert_checklist_datetimes(checklist.model_dump())
    
    # Save checklist
    database.save_checklist(checklist_data, device_id)
    
    return patient


@router.get("/patients", response_model=Patient)
async def get_patient(request: Request):
    """
    Get patient for the device making the request
    """
    device_id = get_device_id(request)
    patient = database.get_patient(device_id)
    if not patient:
        raise HTTPException(status_code=404, detail="No patient found")
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

