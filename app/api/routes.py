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

from app.models.schemas import Patient, QuestionnaireSubmission
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