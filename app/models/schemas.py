"""
Simple data models

- Minimal fields for MVP (intake form basics)
- Pydantic provides automatic validation
- Optional fields for flexibility
- Simple Dict types for questionnaire (can be typed later)
"""
from typing import Optional, Dict, Any
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
    
    CURRENT: Simple dict for answers, optional results dict
    """
    answers: Dict[str, str]           = Field(..., description="Question answers as key-value pairs (question_id -> 'yes'/'no')")
    results: Optional[Dict[str, Any]] = Field(None, description="Calculated results from questionnaire (e.g., eligibility assessment)")


