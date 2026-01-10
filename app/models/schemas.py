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
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=200)
    date_of_birth: str
    email: Optional[str] = None
    phone: Optional[str] = None


class QuestionnaireSubmission(BaseModel):
    """
    Questionnaire submission
    
    CURRENT: Simple dict for answers, optional results dict
    """
    answers: Dict[str, str]
    results: Optional[Dict[str, Any]] = None


