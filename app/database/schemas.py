"""
Simple data models

- Minimal fields for MVP (intake form basics)
- Pydantic provides automatic validation
- Optional fields for flexibility
- Simple Dict types for questionnaire (can be typed later)
"""
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime, date
from pydantic import BaseModel, Field, field_validator, ConfigDict


class PatientCanonical(BaseModel):
    """
    Canonical patient storage model (persisted to disk)
    """
    model_config = ConfigDict(extra="ignore")
    id: Optional[str]            = Field(None, description="Patient unique identifier (auto-generated)")
    name: str                    = Field(...,  description="Patient legal name")
    date_of_birth: str           = Field(...,  description="Date of birth (format: YYYY-MM-DD)")
    sex: Optional[Literal["male", "female", "unknown"]] = Field(None, description="Sex assigned at birth")
    height_cm: Optional[float]   = Field(None, description="Height in centimeters (cm)")
    weight_kg: Optional[float]   = Field(None, description="Weight in kilograms (kg)")
    email: Optional[str]         = Field(None, description="Email address")
    phone: Optional[str]         = Field(None, description="Phone number")
    has_ckd_esrd: Optional[bool] = Field(None, description="Whether patient has CKD or ESRD")
    last_gfr: Optional[float]    = Field(None, description="Last known GFR (Glomerular Filtration Rate) value")
    has_referral: Optional[bool] = Field(None, description="Whether patient already has a referral to a transplant center")

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value: str) -> str:
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("date_of_birth must be in YYYY-MM-DD format")
        if parsed > date.today():
            raise ValueError("date_of_birth cannot be in the future")
        return value

    @field_validator("height_cm")
    @classmethod
    def validate_height_cm(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if not (50 <= value <= 250):
            raise ValueError("height_cm must be between 50 and 250")
        return value

    @field_validator("weight_kg")
    @classmethod
    def validate_weight_kg(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if not (20 <= value <= 300):
            raise ValueError("weight_kg must be between 20 and 300")
        return value


class Patient(BaseModel):
    """
    Patient API response model (includes deprecated aliases).
    """
    id: Optional[str]            = Field(None, description="Patient unique identifier (auto-generated)")
    name: str                    = Field(...,  description="Patient legal name")
    date_of_birth: str           = Field(...,  description="Date of birth (format: YYYY-MM-DD)")
    sex: Optional[Literal["male", "female", "unknown"]] = Field(None, description="Sex assigned at birth")
    height_cm: Optional[float]   = Field(None, description="Height in centimeters (cm)")
    weight_kg: Optional[float]   = Field(None, description="Weight in kilograms (kg)")
    email: Optional[str]         = Field(None, description="Email address")
    phone: Optional[str]         = Field(None, description="Phone number")
    has_ckd_esrd: Optional[bool] = Field(None, description="Whether patient has CKD or ESRD")
    last_gfr: Optional[float]    = Field(None, description="Last known GFR (Glomerular Filtration Rate) value")
    has_referral: Optional[bool] = Field(None, description="Whether patient already has a referral to a transplant center")
    # Deprecated aliases for backward compatibility
    dob: Optional[str]           = Field(None, description="DEPRECATED: alias for date_of_birth")
    sex_assigned_at_birth: Optional[str] = Field(None, description="DEPRECATED: alias for sex")
    height: Optional[float]      = Field(None, description="DEPRECATED: alias for height_cm")
    weight: Optional[float]      = Field(None, description="DEPRECATED: alias for weight_kg")
    weight_lbs: Optional[float]  = Field(None, description="DEPRECATED: derived from weight_kg")


class PatientInput(BaseModel):
    """
    Patient input model (accepts aliases at API boundary)
    """
    id: Optional[str]            = Field(None, description="Patient unique identifier (auto-generated)")
    name: Optional[str]                    = Field(None, description="Patient legal name")
    date_of_birth: Optional[str]           = Field(None, description="Date of birth (format: YYYY-MM-DD)")
    dob: Optional[str]                     = Field(None, description="Date of birth (format: YYYY-MM-DD) - alias for date_of_birth")
    sex: Optional[str]                     = Field(None, description="Sex assigned at birth (e.g., 'male', 'female')")
    sex_assigned_at_birth: Optional[str]   = Field(None, description="Sex assigned at birth (e.g., 'male', 'female') - alias for sex")
    height: Optional[float]                = Field(None, description="Height in centimeters (cm) - alias for height_cm")
    height_cm: Optional[float]             = Field(None, description="Height in centimeters (cm)")
    weight: Optional[float]                = Field(None, description="Weight in kilograms (kg) - legacy alias for weight_kg")
    weight_kg: Optional[float]             = Field(None, description="Weight in kilograms (kg)")
    weight_lbs: Optional[float]            = Field(None, description="Weight in pounds (lbs)")
    email: Optional[str]                   = Field(None, description="Email address")
    phone: Optional[str]                   = Field(None, description="Phone number")
    has_ckd_esrd: Optional[bool]           = Field(None, description="Whether patient has CKD or ESRD")
    last_gfr: Optional[float]              = Field(None, description="Last known GFR (Glomerular Filtration Rate) value")
    has_referral: Optional[bool]           = Field(None, description="Whether patient already has a referral to a transplant center")


class PatientUpdate(PatientInput):
    """
    Patient update model (all fields optional)
    """
    pass


class QuestionnaireSubmission(BaseModel):
    """
    Questionnaire submission
    
    CURRENT: Associated with patient, includes answers only
    Results are computed on the backend from answers
    """
    id: Optional[str]                 = Field(None, description="Unique questionnaire submission ID (auto-generated)")
    patient_id: str                   = Field(..., description="Patient ID this questionnaire is associated with")
    answers: Dict[str, str]           = Field(..., description="Question answers as key-value pairs (question_id -> 'yes'/'no')")
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
    documents: List[str]              = Field(default_factory=list, description="Array of document path names referencing stored documents")


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


class Contraindication(BaseModel):
    """
    Individual contraindication identified in questionnaire
    """
    id: str                           = Field(..., description="Question ID that identified this contraindication")
    question: str                     = Field(..., description="Question text describing the contraindication")


class PatientStatus(BaseModel):
    """
    Patient transplant status based on questionnaire results
    
    CURRENT: Single status per patient, computed from latest questionnaire submission
    """
    id: Optional[str]                                  = Field(None, description="Unique status ID (auto-generated)")
    patient_id: str                                    = Field(..., description="Patient ID this status is associated with")
    has_absolute: bool                                 = Field(..., description="Whether patient has absolute contraindications")
    has_relative: bool                                 = Field(..., description="Whether patient has relative contraindications")
    absolute_contraindications: List[Contraindication] = Field(default_factory=list, description="List of absolute contraindications")
    relative_contraindications: List[Contraindication] = Field(default_factory=list, description="List of relative contraindications")
    pathway_stage: Optional[str]                       = Field(None, description="Current pathway stage: 'identification', 'referral', 'evaluation', 'selection', 'transplantation', 'post-transplant'")
    updated_at: Optional[datetime]                     = Field(default_factory=datetime.now, description="Timestamp when status was last updated")


class FinancialProfile(BaseModel):
    """
    Financial assessment profile for a patient
    
    Stores answers from the financial assessment questionnaire
    """
    id: Optional[str]                 = Field(None, description="Unique financial profile ID (auto-generated)")
    patient_id: str                   = Field(..., description="Patient ID this financial profile is associated with")
    answers: Dict[str, Optional[str]] = Field(..., description="Financial assessment answers as key-value pairs (question_id -> answer or null)")
    submitted_at: Optional[datetime]  = Field(default_factory=datetime.now, description="Timestamp when financial profile was submitted")
    updated_at: Optional[datetime]    = Field(default_factory=datetime.now, description="Timestamp when financial profile was last updated")


class PatientReferralState(BaseModel):
    """
    Patient referral state for Transplant Access Navigator
    
    Tracks patient's referral status and provider information
    """
    patient_id: str                             = Field(..., description="Patient ID")
    location: Dict[str, Any]                    = Field(..., description="Patient location (zip, city, state, optionally lat/lng). City and state can be provided by frontend or derived from zip.")
    has_referral: bool                          = Field(default=False, description="Whether patient has a referral")
    referral_source: Optional[str]              = Field(None, description="Source of referral (nephrologist, pcp, dialysis_center, etc.)")
    last_nephrologist: Optional[Dict[str, Any]] = Field(None, description="Nephrologist information (name, clinic)")
    dialysis_center: Optional[Dict[str, Any]]   = Field(None, description="Dialysis center information (name, social_worker_contact)")
    preferred_centers: List[str]                = Field(default_factory=list, description="List of preferred center IDs")
    referral_status: str                        = Field(default="not_started", description="Status: not_started, in_progress, completed")