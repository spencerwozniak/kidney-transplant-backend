"""
Simple JSON file storage with in-memory caching

- Using JSON files for MVP/demo to avoid database setup complexity
- Single patient assumption simplifies data access (no patient_id lookups needed)
- In-memory cache with TTL reduces file I/O for frequently accessed data
- Easy to migrate to SQL/NoSQL later by replacing these functions
"""
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.database.cache import get_patient_cache, get_status_cache, get_checklist_cache


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
def save_patient(patient: Dict[str, Any], device_id: str):
    """
    Save patient for a specific device
    Stores patients by device_id in separate files
    Invalidates cache to ensure fresh data on next read
    """
    # Store patient in device-specific file
    filepath = f"data/patients/{device_id}.json"
    write_json(filepath, [patient])
    
    # Update cache immediately
    cache = get_patient_cache()
    cache.set(f"patient:{device_id}", patient)


def get_patient(device_id: str) -> Optional[Dict[str, Any]]:
    """
    Get patient for a specific device
    Uses in-memory cache to avoid repeated file reads
    """
    cache = get_patient_cache()
    cache_key = f"patient:{device_id}"
    
    # Check cache first
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    
    # Cache miss - read from file
    filepath = f"data/patients/{device_id}.json"
    patients = read_json(filepath)
    patient = patients[0] if patients else None
    
    # Cache the result (even if None, to avoid repeated file reads)
    if patient is not None:
        cache.set(cache_key, patient)
    
    return patient


def save_questionnaire(questionnaire: Dict[str, Any], device_id: str):
    """
    Save questionnaire for a specific device
    """
    filepath = f"data/questionnaires/{device_id}.json"
    data = read_json(filepath)
    data.append(questionnaire)
    write_json(filepath, data)


def get_questionnaire(device_id: str) -> Optional[Dict[str, Any]]:
    """
    Get questionnaire (most recent for device's patient)
    """
    filepath = f"data/questionnaires/{device_id}.json"
    questionnaires = read_json(filepath)
    if not questionnaires:
        return None
    
    # Get current patient for this device
    patient = get_patient(device_id)
    if not patient:
        return None
    
    patient_id = patient.get('id')
    # Find questionnaires for this patient
    patient_questionnaires = [
        q for q in questionnaires 
        if q.get('patient_id') == patient_id
    ]
    
    if not patient_questionnaires:
        return None
    
    # Return the most recent one (last in list)
    return patient_questionnaires[-1]


def get_all_questionnaires_for_patient(patient_id: str, device_id: str) -> List[Dict[str, Any]]:
    """
    Get all questionnaires for a specific patient
    
    Args:
        patient_id: Patient ID to filter questionnaires by
        device_id: Device ID to get questionnaires from
    
    Returns:
        List of all questionnaire dictionaries for the patient (ordered by submission time)
    """
    filepath = f"data/questionnaires/{device_id}.json"
    questionnaires = read_json(filepath)
    if not questionnaires:
        return []
    
    # Filter questionnaires by patient_id
    patient_questionnaires = [
        q for q in questionnaires 
        if q.get('patient_id') == patient_id
    ]
    
    return patient_questionnaires


def save_checklist(checklist: Dict[str, Any], device_id: str):
    """
    Save checklist for a specific device
    Invalidates cache to ensure fresh data on next read
    """
    filepath = f"data/checklists/{device_id}.json"
    write_json(filepath, [checklist])
    
    # Update cache immediately
    cache = get_checklist_cache()
    cache.set(f"checklist:{device_id}", checklist)


def get_checklist(device_id: str) -> Optional[Dict[str, Any]]:
    """
    Get checklist for a specific device
    Uses in-memory cache to avoid repeated file reads
    """
    cache = get_checklist_cache()
    cache_key = f"checklist:{device_id}"
    
    # Check cache first
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    
    # Cache miss - read from file
    filepath = f"data/checklists/{device_id}.json"
    checklists = read_json(filepath)
    checklist = checklists[0] if checklists else None
    
    # Cache the result (even if None, to avoid repeated file reads)
    if checklist is not None:
        cache.set(cache_key, checklist)
    
    return checklist


def save_patient_status(status: Dict[str, Any], device_id: str):
    """
    Save patient status for a specific device
    Invalidates cache to ensure fresh data on next read
    """
    filepath = f"data/patient_status/{device_id}.json"
    write_json(filepath, [status])
    
    # Update cache immediately
    cache = get_status_cache()
    cache.set(f"status:{device_id}", status)


def get_patient_status(device_id: str) -> Optional[Dict[str, Any]]:
    """
    Get patient status for a specific device
    Uses in-memory cache to avoid repeated file reads
    """
    cache = get_status_cache()
    cache_key = f"status:{device_id}"
    
    # Check cache first
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    
    # Cache miss - read from file
    filepath = f"data/patient_status/{device_id}.json"
    statuses = read_json(filepath)
    status = statuses[0] if statuses else None
    
    # Cache the result (even if None, to avoid repeated file reads)
    if status is not None:
        cache.set(cache_key, status)
    
    return status


def save_financial_profile(profile: Dict[str, Any], device_id: str):
    """
    Save financial profile for a specific device
    """
    filepath = f"data/financial_profiles/{device_id}.json"
    write_json(filepath, [profile])


def get_financial_profile(device_id: str) -> Optional[Dict[str, Any]]:
    """
    Get financial profile for a specific device
    """
    filepath = f"data/financial_profiles/{device_id}.json"
    profiles = read_json(filepath)
    return profiles[0] if profiles else None


def delete_patient(device_id: str):
    """
    Delete patient and all associated records for a specific device
    Also invalidates all caches for this device
    """
    # Get patient ID before deleting patient data
    patient = get_patient(device_id)
    patient_id = patient.get('id') if patient else None
    
    # Invalidate all caches for this device
    patient_cache = get_patient_cache()
    status_cache = get_status_cache()
    checklist_cache = get_checklist_cache()
    patient_cache.invalidate(f"patient:{device_id}")
    status_cache.invalidate(f"status:{device_id}")
    checklist_cache.invalidate(f"checklist:{device_id}")
    
    # Delete patient data file
    path = Path(f"data/patients/{device_id}.json")
    if path.exists():
        path.unlink()
    
    # Delete questionnaire data associated with device
    questionnaire_path = Path(f"data/questionnaires/{device_id}.json")
    if questionnaire_path.exists():
        questionnaire_path.unlink()
    
    # Delete checklist data associated with device
    checklist_path = Path(f"data/checklists/{device_id}.json")
    if checklist_path.exists():
        checklist_path.unlink()
    
    # Delete patient status data
    status_path = Path(f"data/patient_status/{device_id}.json")
    if status_path.exists():
        status_path.unlink()
    
    # Delete financial profile data
    financial_profile_path = Path(f"data/financial_profiles/{device_id}.json")
    if financial_profile_path.exists():
        financial_profile_path.unlink()
    
    # Delete patient's document directory and all its contents
    if patient_id:
        documents_dir = Path("data/documents") / patient_id
        if documents_dir.exists() and documents_dir.is_dir():
            shutil.rmtree(documents_dir)
    
    # Delete patient referral state
    referral_state_path = Path(f"data/patient_referral_states/{device_id}.json")
    if referral_state_path.exists():
        referral_state_path.unlink()


def save_patient_referral_state(state: Dict[str, Any], device_id: str):
    """
    Save patient referral state for a specific device
    """
    filepath = f"data/patient_referral_states/{device_id}.json"
    write_json(filepath, [state])


def get_patient_referral_state(device_id: str) -> Optional[Dict[str, Any]]:
    """
    Get patient referral state for a specific device
    """
    filepath = f"data/patient_referral_states/{device_id}.json"
    states = read_json(filepath)
    return states[0] if states else None

