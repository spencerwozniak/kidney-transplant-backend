"""
Simple JSON file storage

- Using JSON files for MVP/demo to avoid database setup complexity
- Single patient assumption simplifies data access (no patient_id lookups needed)
- Easy to migrate to SQL/NoSQL later by replacing these functions
"""
import json
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


def delete_patient():
    """
    Delete patient (demo: only one)
    CURRENT: Single patient assumption, deletes patient.json file
    """
    path = Path("data/patient.json")
    if path.exists():
        path.unlink()
    # Also clear questionnaire data associated with patient
    questionnaire_path = Path("data/questionnaire.json")
    if questionnaire_path.exists():
        questionnaire_path.unlink()
    # Also clear checklist data associated with patient
    checklist_path = Path("data/checklist.json")
    if checklist_path.exists():
        checklist_path.unlink()