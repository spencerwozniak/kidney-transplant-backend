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


@router.post("/questionnaire")
async def submit_questionnaire(submission: QuestionnaireSubmission):
    """
    Save questionnaire
    
    CURRENT: Simple save, verifies patient exists, adds ID and timestamp
    """
    # Verify patient exists
    if not database.get_patient():
        raise HTTPException(status_code=404, detail="Patient not found")
    
    data = submission.model_dump()
    data['id'] = str(uuid.uuid4())
    data['created_at'] = datetime.now().isoformat()
    database.save_questionnaire(data)
    return data