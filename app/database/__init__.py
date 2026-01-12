"""
Database module

Contains both data models (schemas) and storage operations.
"""

# Export schemas
from app.database.schemas import (
    Patient,
    QuestionnaireSubmission,
    TransplantChecklist,
    ChecklistItem,
    PatientStatus,
    Contraindication,
    FinancialProfile,
    PatientReferralState,
)

# Export storage functions for convenience
from app.database.storage import (
    read_json,
    write_json,
    save_patient,
    get_patient,
    save_questionnaire,
    get_questionnaire,
    get_all_questionnaires_for_patient,
    save_checklist,
    get_checklist,
    save_patient_status,
    get_patient_status,
    save_financial_profile,
    get_financial_profile,
    delete_patient,
    save_patient_referral_state,
    get_patient_referral_state,
)

# For backward compatibility, also export as 'storage' module
from app.database import storage

__all__ = [
    # Schemas
    "Patient",
    "QuestionnaireSubmission",
    "TransplantChecklist",
    "ChecklistItem",
    "PatientStatus",
    "Contraindication",
    "FinancialProfile",
    "PatientReferralState",
    # Storage functions
    "read_json",
    "write_json",
    "save_patient",
    "get_patient",
    "save_questionnaire",
    "get_questionnaire",
    "get_all_questionnaires_for_patient",
    "save_checklist",
    "get_checklist",
    "save_patient_status",
    "get_patient_status",
    "save_financial_profile",
    "get_financial_profile",
    "delete_patient",
    "save_patient_referral_state",
    "get_patient_referral_state",
    # Storage module
    "storage",
]
