"""
Questionnaire submission endpoints
"""
from fastapi import APIRouter, HTTPException
import uuid

from app.database.schemas import QuestionnaireSubmission
from app.database import storage as database
from app.services.status.computation import compute_patient_status_from_all_questionnaires
from app.services.utils import convert_datetime_to_iso

router = APIRouter()


@router.get("/questionnaire", response_model=QuestionnaireSubmission)
async def get_questionnaire():
    """
    Get patient questionnaire
    
    CURRENT: Returns the most recent questionnaire for the current patient
    """
    questionnaire = database.get_questionnaire()
    if not questionnaire:
        raise HTTPException(status_code=404, detail="Questionnaire not found")
    
    return QuestionnaireSubmission(**questionnaire)


@router.post("/questionnaire", response_model=QuestionnaireSubmission)
async def submit_questionnaire(submission: QuestionnaireSubmission):
    """
    Save questionnaire
    
    CURRENT: Verifies patient exists, adds ID, stores with patient_id and timestamp
    Also computes and saves patient status from questionnaire results
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
    data = convert_datetime_to_iso(submission.model_dump(), ['submitted_at'])
    
    # Save to database
    database.save_questionnaire(data)
    
    # Recompute patient status from all questionnaires (rollup)
    status = compute_patient_status_from_all_questionnaires(submission.patient_id)
    status.id = str(uuid.uuid4())
    
    # Prepare status data for storage
    status_data = convert_datetime_to_iso(status.model_dump(), ['updated_at'])
    
    # Save patient status
    database.save_patient_status(status_data)
    
    # Return the submission with generated ID
    return submission

