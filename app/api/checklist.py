"""
Checklist management endpoints
"""
from fastapi import APIRouter, HTTPException, Body
import uuid
from datetime import datetime

from app.models.schemas import TransplantChecklist
from app.core import database
from app.services.checklist_initialization import create_default_checklist
from app.services.utils import convert_checklist_datetimes

router = APIRouter()


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
        checklist_data = convert_checklist_datetimes(new_checklist.model_dump())
        
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
    data = convert_checklist_datetimes(checklist.model_dump())
    
    # Save to database
    database.save_checklist(data)
    
    # Return the checklist with generated ID
    return checklist


@router.patch("/checklist/items/{item_id}", response_model=TransplantChecklist)
async def update_checklist_item(
    item_id: str,
    update_data: dict = Body(...),
):
    """
    Update a specific checklist item
    
    CURRENT: Updates is_complete, completed_at, and/or notes for a checklist item
    """
    # Verify patient exists
    patient = database.get_patient()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Get current checklist
    checklist_data = database.get_checklist()
    if not checklist_data:
        raise HTTPException(status_code=404, detail="No checklist found")
    
    # Find the item to update
    item_found = False
    for item in checklist_data.get('items', []):
        if item.get('id') == item_id:
            item_found = True
            # Update fields if provided
            if 'is_complete' in update_data:
                item['is_complete'] = update_data['is_complete']
                # If marking as incomplete, clear completed_at
                if update_data['is_complete'] is False:
                    item['completed_at'] = None
            if 'completed_at' in update_data:
                item['completed_at'] = update_data['completed_at']
            if 'notes' in update_data:
                item['notes'] = update_data['notes'] if update_data['notes'] else None
            break
    
    if not item_found:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    
    # Update checklist updated_at timestamp
    checklist_data['updated_at'] = datetime.now().isoformat()
    
    # Save updated checklist
    database.save_checklist(checklist_data)
    
    # Return updated checklist
    return checklist_data

