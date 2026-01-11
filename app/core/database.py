"""
Simple JSON file storage

- Using JSON files for MVP/demo to avoid database setup complexity
- Single patient assumption simplifies data access (no patient_id lookups needed)
- Easy to migrate to SQL/NoSQL later by replacing these functions
"""
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional


def read_json(filepath: str) -> List[Dict[str, Any]]:
    """
    Read JSON file, return empty list if not found
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def write_json(filepath: str, data: List[Dict[str, Any]]):
    """
    Write data to JSON file
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


# Simple storage functions
def save_patient(patient: Dict[str, Any]):
    """
    Save patient (replace existing for demo)
    CURRENT: Single patient assumption, overwrites existing
    """
    write_json("data/patient.json", [patient])


def get_patient() -> Optional[Dict[str, Any]]:
    """
    Get patient (demo: only one)
    CURRENT: Single patient assumption, no ID needed
    """
    patients = read_json("data/patient.json")
    return patients[0] if patients else None


def save_questionnaire(questionnaire: Dict[str, Any]):
    """
    Save questionnaire
    
    CURRENT: Single patient assumption
    """
    data = read_json("data/questionnaire.json")
    data.append(questionnaire)
    write_json("data/questionnaire.json", data)


def save_checklist(checklist: Dict[str, Any]):
    """
    Save checklist (replace existing for demo)
    CURRENT: Single patient assumption, overwrites existing
    """
    write_json("data/checklist.json", [checklist])


def get_checklist() -> Optional[Dict[str, Any]]:
    """
    Get checklist (demo: only one)
    CURRENT: Single patient assumption, no ID needed
    """
    checklists = read_json("data/checklist.json")
    return checklists[0] if checklists else None


def save_patient_status(status: Dict[str, Any]):
    """
    Save patient status (replace existing for demo)
    CURRENT: Single patient assumption, overwrites existing
    """
    write_json("data/patient_status.json", [status])


def get_patient_status() -> Optional[Dict[str, Any]]:
    """
    Get patient status (demo: only one)
    CURRENT: Single patient assumption, no ID needed
    """
    statuses = read_json("data/patient_status.json")
    return statuses[0] if statuses else None


def save_financial_profile(profile: Dict[str, Any]):
    """
    Save financial profile (replace existing for demo)
    CURRENT: Single patient assumption, overwrites existing
    """
    write_json("data/financial_profile.json", [profile])


def get_financial_profile() -> Optional[Dict[str, Any]]:
    """
    Get financial profile (demo: only one)
    CURRENT: Single patient assumption, no ID needed
    """
    profiles = read_json("data/financial_profile.json")
    return profiles[0] if profiles else None


def delete_patient():
    """
    Delete patient and all associated records (demo: only one)
    CURRENT: Single patient assumption, deletes patient.json file and all associated data
    """
    # Get patient ID before deleting patient data
    patient = get_patient()
    patient_id = patient.get('id') if patient else None
    
    # Delete patient data file
    path = Path("data/patient.json")
    if path.exists():
        path.unlink()
    
    # Delete questionnaire data associated with patient
    questionnaire_path = Path("data/questionnaire.json")
    if questionnaire_path.exists():
        questionnaire_path.unlink()
    
    # Delete checklist data associated with patient
    checklist_path = Path("data/checklist.json")
    if checklist_path.exists():
        checklist_path.unlink()
    
    # Delete patient status data
    status_path = Path("data/patient_status.json")
    if status_path.exists():
        status_path.unlink()
    
    # Delete financial profile data
    financial_profile_path = Path("data/financial_profile.json")
    if financial_profile_path.exists():
        financial_profile_path.unlink()
    
    # Delete patient's document directory and all its contents
    if patient_id:
        documents_dir = Path("data/documents") / patient_id
        if documents_dir.exists() and documents_dir.is_dir():
            shutil.rmtree(documents_dir)
    
    # Delete patient referral state
    referral_state_path = Path("data/patient_referral_state.json")
    if referral_state_path.exists():
        referral_state_path.unlink()


def save_patient_referral_state(state: Dict[str, Any]):
    """
    Save patient referral state (replace existing for demo)
    CURRENT: Single patient assumption, overwrites existing
    """
    write_json("data/patient_referral_state.json", [state])


def get_patient_referral_state() -> Optional[Dict[str, Any]]:
    """
    Get patient referral state (demo: only one)
    CURRENT: Single patient assumption, no ID needed
    """
    states = read_json("data/patient_referral_state.json")
    return states[0] if states else None