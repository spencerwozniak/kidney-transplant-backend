"""
Patient management endpoints
"""
from fastapi import APIRouter, HTTPException
import uuid

from app.models.schemas import Patient
from app.core import database
from app.services.checklist_initialization import create_default_checklist
from app.services.utils import convert_checklist_datetimes

router = APIRouter()


@router.post("/patients", response_model=Patient)
async def create_patient(patient: Patient):
    """
    Save patient (intake form)
    
    CURRENT: Single patient, generates UUID, saves directly
    Automatically creates default checklist for new patient
    """
    patient.id = str(uuid.uuid4())
    database.save_patient(patient.model_dump())
    
    # Create default checklist for new patient
    checklist = create_default_checklist(patient.id)
    checklist.id = str(uuid.uuid4())
    
    # Prepare checklist data for storage
    checklist_data = convert_checklist_datetimes(checklist.model_dump())
    
    # Save checklist
    database.save_checklist(checklist_data)
    
    return patient


@router.get("/patients", response_model=Patient)
async def get_patient():
    """
    Get patient
    
    CURRENT: Returns single patient (no ID needed)
    """
    patient = database.get_patient()
    if not patient:
        raise HTTPException(status_code=404, detail="No patient found")
    return patient


@router.delete("/patients")
async def delete_patient():
    """
    Delete patient and associated data
    
    CURRENT: Single patient assumption, deletes patient, questionnaire, checklist, and status data
    Returns 404 if no patient exists to ensure DELETE never silently fails
    """
    # Check if patient exists before deletion
    patient = database.get_patient()
    if not patient:
        raise HTTPException(status_code=404, detail="No patient found")
    
    # Delete patient and all associated data
    database.delete_patient()
    return {"message": "Patient deleted successfully"}

