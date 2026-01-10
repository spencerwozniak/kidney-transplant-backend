"""
Simple data models

- Minimal fields for MVP (intake form basics)
- Pydantic provides automatic validation
- Optional fields for flexibility
- Simple Dict types for questionnaire (can be typed later)
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class Patient(BaseModel):
    """
    Patient model
    
    CURRENT: Basic intake form fields
    """
    id: Optional[str]       = Field(None, description="Patient unique identifier (auto-generated)")
    name: str               = Field(...,  description="Patient legal name")
    date_of_birth: str      = Field(...,  description="Date of birth (format: YYYY-MM-DD)")
    sex: Optional[str]      = Field(None, description="Sex assigned at birth (e.g., 'male', 'female')")
    height: Optional[float] = Field(None, description="Height in centimeters (cm)")
    weight: Optional[float] = Field(None, description="Weight in kilograms (kg)")
    email: Optional[str]    = Field(None, description="Email address")
    phone: Optional[str]    = Field(None, description="Phone number")


class QuestionnaireSubmission(BaseModel):
    """
    Questionnaire submission
    
    CURRENT: Associated with patient, includes answers and results
    """
    id: Optional[str]                 = Field(None, description="Unique questionnaire submission ID (auto-generated)")
    patient_id: str                   = Field(..., description="Patient ID this questionnaire is associated with")
    answers: Dict[str, str]           = Field(..., description="Question answers as key-value pairs (question_id -> 'yes'/'no')")
    results: Optional[Dict[str, Any]] = Field(None, description="Calculated results from questionnaire (e.g., eligibility assessment)")
    submitted_at: Optional[datetime]  = Field(default_factory=datetime.now, description="Timestamp when questionnaire was submitted")


class ChecklistItem(BaseModel):
    """
    Individual checklist item for pre-transplant evaluation
    
    Represents one step in the pre-transplant workup process
    """
    id: str                           = Field(..., description="Unique identifier for the checklist item (e.g., 'physical_exam', 'lab_work')")
    title: str                        = Field(..., description="Display title of the checklist item")
    description: Optional[str]        = Field(None, description="Detailed description of what this evaluation entails")
    is_complete: bool                 = Field(default=False, description="Whether this item has been completed")
    notes: Optional[str]              = Field(None, description="Patient notes about where records are stored or other details")
    completed_at: Optional[datetime]  = Field(None, description="Timestamp when item was marked complete")
    order: int                        = Field(..., description="Display order in the checklist (1-based)")


class TransplantChecklist(BaseModel):
    """
    Pre-transplant checklist for a patient
    
    Tracks progress through required evaluations and tests before transplant listing
    """
    id: Optional[str]                 = Field(None, description="Unique checklist ID (auto-generated)")
    patient_id: str                   = Field(..., description="Patient ID this checklist is associated with")
    items: List[ChecklistItem]        = Field(..., description="List of checklist items")
    created_at: Optional[datetime]    = Field(default_factory=datetime.now, description="Timestamp when checklist was created")
    updated_at: Optional[datetime]    = Field(default_factory=datetime.now, description="Timestamp when checklist was last updated")