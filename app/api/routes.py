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

from app.models.schemas import Patient, QuestionnaireSubmission, TransplantChecklist, PatientStatus
from app.core import database
from app.services.status_computation import compute_patient_status
from app.services.checklist_initialization import create_default_checklist

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
    checklist_data = checklist.model_dump()
    # Convert datetime objects to ISO strings for JSON storage
    if isinstance(checklist_data.get('created_at'), datetime):
        checklist_data['created_at'] = checklist_data['created_at'].isoformat()
    if isinstance(checklist_data.get('updated_at'), datetime):
        checklist_data['updated_at'] = checklist_data['updated_at'].isoformat()
    
    # Convert datetime objects in checklist items
    for item in checklist_data.get('items', []):
        if isinstance(item.get('completed_at'), datetime):
            item['completed_at'] = item['completed_at'].isoformat()
    
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
    data = submission.model_dump()
    # Convert datetime to ISO string for JSON storage
    if isinstance(data.get('submitted_at'), datetime):
        data['submitted_at'] = data['submitted_at'].isoformat()
    
    # Save to database
    database.save_questionnaire(data)
    
    # Compute patient status from answers (backend computation)
    status = compute_patient_status(submission.answers, submission.patient_id)
    status.id = str(uuid.uuid4())
    
    # Prepare status data for storage
    status_data = status.model_dump()
    # Convert datetime to ISO string for JSON storage
    if isinstance(status_data.get('updated_at'), datetime):
        status_data['updated_at'] = status_data['updated_at'].isoformat()
    
    # Save patient status
    database.save_patient_status(status_data)
    
    # Return the submission with generated ID
    return submission


@router.get("/patient-status", response_model=PatientStatus)
async def get_patient_status():
    """
    Get patient status
    
    CURRENT: Returns single patient status (no ID needed)
    """
    status = database.get_patient_status()
    if not status:
        raise HTTPException(status_code=404, detail="No patient status found")
    return status


@router.delete("/patients")
async def delete_patient():
    """
    Delete patient and associated data
    
    CURRENT: Single patient assumption, deletes patient, questionnaire, checklist, and status data
    """
    database.delete_patient()
    return {"message": "Patient deleted successfully"}


@router.get("/checklist", response_model=TransplantChecklist)
async def get_checklist():
    """
    Get checklist for current patient
    
    CURRENT: Returns single checklist (no ID needed)
    If no checklist exists, creates default one for current patient
    """
    checklist = database.get_checklist()
    if not checklist:
        # Get patient to create checklist for
        patient = database.get_patient()
        if not patient:
            raise HTTPException(status_code=404, detail="No patient found")
        
        # Create default checklist
        new_checklist = create_default_checklist(patient.get('id'))
        new_checklist.id = str(uuid.uuid4())
        
        # Prepare checklist data for storage
        checklist_data = new_checklist.model_dump()
        # Convert datetime objects to ISO strings for JSON storage
        if isinstance(checklist_data.get('created_at'), datetime):
            checklist_data['created_at'] = checklist_data['created_at'].isoformat()
        if isinstance(checklist_data.get('updated_at'), datetime):
            checklist_data['updated_at'] = checklist_data['updated_at'].isoformat()
        
        # Convert datetime objects in checklist items
        for item in checklist_data.get('items', []):
            if isinstance(item.get('completed_at'), datetime):
                item['completed_at'] = item['completed_at'].isoformat()
        
        # Save checklist
        database.save_checklist(checklist_data)
        
        return new_checklist
    
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