"""
Financial profile endpoints
"""
from fastapi import APIRouter, HTTPException
import uuid

from app.models.schemas import FinancialProfile
from app.core import database
from app.services.utils import convert_datetime_to_iso

router = APIRouter()


@router.post("/financial-profile", response_model=FinancialProfile)
async def save_financial_profile(profile: FinancialProfile):
    """
    Save financial profile (auto-save during questionnaire)
    
    CURRENT: Verifies patient exists, adds/updates ID, stores with patient_id and timestamp
    This endpoint is used for both auto-save (partial answers) and final submission
    """
    # Verify patient exists
    patient = database.get_patient()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Verify patient_id matches current patient (for single patient demo)
    if profile.patient_id != patient.get('id'):
        raise HTTPException(status_code=400, detail="Patient ID does not match current patient")
    
    # Get existing financial profile if it exists
    existing_profile = database.get_financial_profile()
    
    # If profile exists, merge answers (update existing, add new)
    if existing_profile:
        existing_answers = existing_profile.get('answers', {})
        # Merge new answers with existing ones
        merged_answers = {**existing_answers, **profile.answers}
        profile.answers = merged_answers
        profile.id = existing_profile.get('id')
    else:
        # Generate ID if not provided and no existing profile
        if not profile.id:
            profile.id = str(uuid.uuid4())
    
    # Prepare data for storage
    data = convert_datetime_to_iso(profile.model_dump(), ['submitted_at', 'updated_at'])
    
    # Save to database
    database.save_financial_profile(data)
    
    # Return the profile with generated/updated ID
    return profile


@router.post("/financial-profile/submit", response_model=FinancialProfile)
async def submit_financial_profile(profile: FinancialProfile):
    """
    Submit final financial profile
    
    CURRENT: Similar to save_financial_profile but marks as final submission
    Sets submitted_at timestamp
    """
    # Verify patient exists
    patient = database.get_patient()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Verify patient_id matches current patient (for single patient demo)
    if profile.patient_id != patient.get('id'):
        raise HTTPException(status_code=400, detail="Patient ID does not match current patient")
    
    # Get existing financial profile if it exists
    existing_profile = database.get_financial_profile()
    
    # If profile exists, merge answers (update existing, add new)
    if existing_profile:
        existing_answers = existing_profile.get('answers', {})
        # Merge new answers with existing ones
        merged_answers = {**existing_answers, **profile.answers}
        profile.answers = merged_answers
        profile.id = existing_profile.get('id')
    else:
        # Generate ID if not provided and no existing profile
        if not profile.id:
            profile.id = str(uuid.uuid4())
    
    # Prepare data for storage
    data = convert_datetime_to_iso(profile.model_dump(), ['submitted_at', 'updated_at'])
    
    # Save to database
    database.save_financial_profile(data)
    
    # Return the profile with generated/updated ID
    return profile


@router.get("/financial-profile", response_model=FinancialProfile)
async def get_financial_profile():
    """
    Get financial profile
    
    CURRENT: Returns single financial profile (no ID needed, single patient assumption)
    """
    profile = database.get_financial_profile()
    if not profile:
        raise HTTPException(status_code=404, detail="No financial profile found")
    return profile

