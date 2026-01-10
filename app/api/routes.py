"""
Basic API endpoints

- Minimal endpoints for MVP: create/get patient, submit questionnaire
- No authentication (single patient demo)
- Direct database calls
- Simple error handling
"""
from fastapi import APIRouter, HTTPException
import uuid
from datetime import datetime

from app.models.schemas import Patient, QuestionnaireSubmission, TransplantChecklist
from app.core import database

router = APIRouter()

@router.post("/patients", response_model=Patient)
async def create_patient(patient: Patient):
    """
    Save patient (intake form)
    
    CURRENT: Single patient, generates UUID, saves directly
    """
    patient.id = str(uuid.uuid4())
    database.save_patient(patient.model_dump())
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


@router.post("/questionnaire", response_model=QuestionnaireSubmission)
async def submit_questionnaire(submission: QuestionnaireSubmission):
    """
    Save questionnaire
    
    CURRENT: Verifies patient exists, adds ID, stores with patient_id and timestamp
    """
    # Verify patient exists
    patient = database.get_patient()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Verify patient_id matches current patient (for single patient demo)
    if submission.patient_id != patient.get('id'):
        raise HTTPException(status_code=400, detail="Patient ID does not match current patient")
    
    # Generate ID if not provided
    if not submission.id:
        submission.id = str(uuid.uuid4())
    
    # Prepare data for storage
    data = submission.model_dump()
    # Convert datetime to ISO string for JSON storage
    if isinstance(data.get('submitted_at'), datetime):
        data['submitted_at'] = data['submitted_at'].isoformat()
    
    # Save to database
    database.save_questionnaire(data)
    
    # Return the submission with generated ID
    return submission


@router.delete("/patients")
async def delete_patient():
    """
    Delete patient and associated data
    
    CURRENT: Single patient assumption, deletes patient and questionnaire data
    """
    database.delete_patient()
    return {"message": "Patient deleted successfully"}


@router.get("/checklist", response_model=TransplantChecklist)
async def get_checklist():
    """
    Get checklist for current patient
    
    CURRENT: Returns single checklist (no ID needed)
    """
    checklist = database.get_checklist()
    if not checklist:
        raise HTTPException(status_code=404, detail="No checklist found")
    return checklist


@router.post("/checklist", response_model=TransplantChecklist)
async def create_or_update_checklist(checklist: TransplantChecklist):
    """
    Create or update checklist
    
    CURRENT: Single patient, generates UUID if needed, saves directly
    """
    # Verify patient exists
    patient = database.get_patient()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Verify patient_id matches current patient (for single patient demo)
    if checklist.patient_id != patient.get('id'):
        raise HTTPException(status_code=400, detail="Patient ID does not match current patient")
    
    # Generate ID if not provided
    if not checklist.id:
        checklist.id = str(uuid.uuid4())
    
    # Prepare data for storage
    data = checklist.model_dump()
    # Convert datetime objects to ISO strings for JSON storage
    if isinstance(data.get('created_at'), datetime):
        data['created_at'] = data['created_at'].isoformat()
    if isinstance(data.get('updated_at'), datetime):
        data['updated_at'] = data['updated_at'].isoformat()
    
    # Convert datetime objects in checklist items
    for item in data.get('items', []):
        if isinstance(item.get('completed_at'), datetime):
            item['completed_at'] = item['completed_at'].isoformat()
    
    # Save to database
    database.save_checklist(data)
    
    # Return the checklist with generated ID
    return checklist