"""
API route tests - verifies endpoints and database file creation
"""
import pytest
import json
import os
import tempfile
import shutil
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.core import database


@pytest.fixture
def temp_data_dir():
    """Create temporary data directory for tests"""
    temp_dir = tempfile.mkdtemp()
    original_data_dir = "data"
    
    # Patch the database functions to use temp directory
    original_save_patient = database.save_patient
    original_get_patient = database.get_patient
    original_save_questionnaire = database.save_questionnaire
    original_get_all_questionnaires = database.get_all_questionnaires_for_patient
    original_get_checklist = database.get_checklist
    original_save_patient_status = database.save_patient_status
    
    # Patch load_questions to use temp directory (demo-safe: returns [] if file missing)
    from app.services import status_computation
    original_load_questions = status_computation.load_questions
    
    def temp_load_questions():
        questions_path = Path(temp_dir) / "questions.json"
        try:
            with open(questions_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Demo-safe fallback: return empty list if questions.json is missing
            return []
    
    status_computation.load_questions = temp_load_questions
    
    # Create minimal questions.json for tests that need it (optional - tests should work without it too)
    minimal_questions = [
        {
            "id": "metastatic_cancer",
            "category": "absolute",
            "question": "Do you have metastatic cancer?",
            "description": "Test question"
        },
        {
            "id": "decompensated_cirrhosis",
            "category": "absolute",
            "question": "Do you have decompensated cirrhosis?",
            "description": "Test question"
        },
        {
            "id": "severe_lung_disease",
            "category": "relative",
            "question": "Do you have severe lung disease?",
            "description": "Test question"
        },
        {
            "id": "q1",
            "category": "absolute",
            "question": "Test question 1?",
            "description": "Test question"
        }
    ]
    os.makedirs(temp_dir, exist_ok=True)
    with open(f"{temp_dir}/questions.json", 'w') as f:
        json.dump(minimal_questions, f, indent=2)
    
    def temp_save_patient(patient):
        os.makedirs(temp_dir, exist_ok=True)
        with open(f"{temp_dir}/patient.json", 'w') as f:
            json.dump([patient], f, indent=2)
    
    def temp_get_patient():
        try:
            with open(f"{temp_dir}/patient.json", 'r') as f:
                patients = json.load(f)
                return patients[0] if patients else None
        except (FileNotFoundError, json.JSONDecodeError):
            return None
    
    def temp_save_questionnaire(questionnaire):
        os.makedirs(temp_dir, exist_ok=True)
        try:
            with open(f"{temp_dir}/questionnaire.json", 'r') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = []
        data.append(questionnaire)
        with open(f"{temp_dir}/questionnaire.json", 'w') as f:
            json.dump(data, f, indent=2)
    
    def temp_get_all_questionnaires_for_patient(patient_id):
        try:
            with open(f"{temp_dir}/questionnaire.json", 'r') as f:
                questionnaires = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
        return [q for q in questionnaires if q.get('patient_id') == patient_id]
    
    def temp_get_checklist():
        try:
            with open(f"{temp_dir}/checklist.json", 'r') as f:
                checklists = json.load(f)
                return checklists[0] if checklists else None
        except (FileNotFoundError, json.JSONDecodeError):
            return None
    
    def temp_save_patient_status(status):
        os.makedirs(temp_dir, exist_ok=True)
        with open(f"{temp_dir}/patient_status.json", 'w') as f:
            json.dump([status], f, indent=2)
    
    # Monkey patch for test
    database.save_patient = temp_save_patient
    database.get_patient = temp_get_patient
    database.save_questionnaire = temp_save_questionnaire
    database.get_all_questionnaires_for_patient = temp_get_all_questionnaires_for_patient
    database.get_checklist = temp_get_checklist
    database.save_patient_status = temp_save_patient_status
    
    yield temp_dir
    
    # Restore original functions
    database.save_patient = original_save_patient
    database.get_patient = original_get_patient
    database.save_questionnaire = original_save_questionnaire
    database.get_all_questionnaires_for_patient = original_get_all_questionnaires
    database.get_checklist = original_get_checklist
    database.save_patient_status = original_save_patient_status
    status_computation.load_questions = original_load_questions
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def client():
    """Test client"""
    return TestClient(app)


def test_root(client):
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_patient(client, temp_data_dir):
    """Test creating a patient and verify database file is created"""
    patient_data = {
        "name": "John Doe",
        "date_of_birth": "1980-01-15",
        "email": "john@example.com",
        "phone": "555-1234"
    }
    
    response = client.post("/api/v1/patients", json=patient_data)
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "John Doe"
    assert data["email"] == "john@example.com"
    assert data["id"] is not None  # UUID should be generated
    
    # Verify database file was created
    patient_file = Path(temp_data_dir) / "patient.json"
    assert patient_file.exists(), f"Patient file should be created at {patient_file}"
    
    # Verify file contents
    with open(patient_file, 'r') as f:
        saved_data = json.load(f)
        assert len(saved_data) == 1
        assert saved_data[0]["name"] == "John Doe"
        assert saved_data[0]["id"] == data["id"]


def test_get_patient_not_found(client, temp_data_dir):
    """Test getting patient when none exists"""
    response = client.get("/api/v1/patients")
    assert response.status_code == 404
    assert "No patient found" in response.json()["detail"]


def test_get_patient(client, temp_data_dir):
    """Test getting a patient after creating one"""
    # Create patient first
    patient_data = {
        "name": "Jane Smith",
        "date_of_birth": "1975-05-20",
        "email": "jane@example.com"
    }
    create_response = client.post("/api/v1/patients", json=patient_data)
    assert create_response.status_code == 200
    created_id = create_response.json()["id"]
    
    # Get patient
    response = client.get("/api/v1/patients")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Jane Smith"
    assert data["id"] == created_id


def test_submit_questionnaire_no_patient(client, temp_data_dir):
    """Test submitting questionnaire when no patient exists"""
    questionnaire_data = {
        "patient_id": "test-id",
        "answers": {"q1": "yes", "q2": "no"},
        "results": {"eligible": False}
    }
    
    response = client.post("/api/v1/questionnaire", json=questionnaire_data)
    assert response.status_code == 404
    assert "Patient not found" in response.json()["detail"]


def test_submit_questionnaire(client, temp_data_dir):
    """Test submitting questionnaire and verify database file is created"""
    # Create patient first
    patient_data = {
        "name": "Test Patient",
        "date_of_birth": "1990-01-01",
        "email": "test@example.com"
    }
    patient_response = client.post("/api/v1/patients", json=patient_data)
    patient_id = patient_response.json()["id"]
    
    # Submit questionnaire
    questionnaire_data = {
        "patient_id": patient_id,
        "answers": {
            "metastatic_cancer": "no",
            "decompensated_cirrhosis": "no",
            "severe_lung_disease": "no"
        }
    }
    
    response = client.post("/api/v1/questionnaire", json=questionnaire_data)
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["patient_id"] == patient_id
    assert data["answers"] == questionnaire_data["answers"]
    assert data["id"] is not None
    assert "submitted_at" in data
    
    # Verify database file was created
    questionnaire_file = Path(temp_data_dir) / "questionnaire.json"
    assert questionnaire_file.exists(), f"Questionnaire file should be created at {questionnaire_file}"
    
    # Verify file contents
    with open(questionnaire_file, 'r') as f:
        saved_data = json.load(f)
        assert len(saved_data) == 1
        assert saved_data[0]["patient_id"] == patient_id
        assert saved_data[0]["answers"] == questionnaire_data["answers"]
        assert saved_data[0]["id"] == data["id"]


def test_submit_multiple_questionnaires(client, temp_data_dir):
    """Test that multiple questionnaires are appended, not overwritten"""
    # Create patient
    patient_response = client.post("/api/v1/patients", json={
        "name": "Test",
        "date_of_birth": "1990-01-01"
    })
    patient_id = patient_response.json()["id"]
    
    # Submit first questionnaire
    response1 = client.post("/api/v1/questionnaire", json={
        "patient_id": patient_id,
        "answers": {"q1": "yes"},
        "results": {}
    })
    id1 = response1.json()["id"]
    
    # Submit second questionnaire
    response2 = client.post("/api/v1/questionnaire", json={
        "patient_id": patient_id,
        "answers": {"q1": "no"},
        "results": {}
    })
    id2 = response2.json()["id"]
    
    # Verify both are saved
    questionnaire_file = Path(temp_data_dir) / "questionnaire.json"
    with open(questionnaire_file, 'r') as f:
        saved_data = json.load(f)
        assert len(saved_data) == 2
        assert saved_data[0]["id"] == id1
        assert saved_data[1]["id"] == id2
        assert saved_data[0]["patient_id"] == patient_id
        assert saved_data[1]["patient_id"] == patient_id


def test_patient_validation(client):
    """Test that patient validation works (required fields)"""
    # Missing required field
    response = client.post("/api/v1/patients", json={
        "date_of_birth": "1990-01-01"
        # Missing name
    })
    assert response.status_code == 422  # Validation error


def test_questionnaire_wrong_patient_id(client, temp_data_dir):
    """Test that questionnaire with wrong patient_id is rejected"""
    # Create patient
    patient_response = client.post("/api/v1/patients", json={
        "name": "Test Patient",
        "date_of_birth": "1990-01-01"
    })
    correct_patient_id = patient_response.json()["id"]
    
    # Try to submit questionnaire with wrong patient_id
    response = client.post("/api/v1/questionnaire", json={
        "patient_id": "wrong-id-123",
        "answers": {"q1": "yes"},
        "results": {}
    })
    
    assert response.status_code == 400
    assert "Patient ID does not match" in response.json()["detail"]


def test_patient_status_rollup_across_questionnaires(client, temp_data_dir):
    """Test that patient status rolls up contraindications across all questionnaires"""
    # 1) Create patient
    patient_response = client.post("/api/v1/patients", json={
        "name": "Test Patient",
        "date_of_birth": "1990-01-01",
        "email": "test@example.com"
    })
    patient_id = patient_response.json()["id"]
    
    # 2) Submit questionnaire 1 with no contraindications
    questionnaire1_data = {
        "patient_id": patient_id,
        "answers": {
            "metastatic_cancer": "no",
            "decompensated_cirrhosis": "no",
            "severe_lung_disease": "no"
        }
    }
    response1 = client.post("/api/v1/questionnaire", json=questionnaire1_data)
    assert response1.status_code == 200
    
    # 3) GET patient-status => has_absolute=false, has_relative=false
    status_response1 = client.get("/api/v1/patient-status")
    assert status_response1.status_code == 200
    status_data1 = status_response1.json()
    assert status_data1["has_absolute"] is False
    assert status_data1["has_relative"] is False
    assert len(status_data1["absolute_contraindications"]) == 0
    assert len(status_data1["relative_contraindications"]) == 0
    
    # 4) Submit questionnaire 2 with an absolute contraindication
    questionnaire2_data = {
        "patient_id": patient_id,
        "answers": {
            "metastatic_cancer": "yes",  # Absolute contraindication
            "decompensated_cirrhosis": "no",
            "severe_lung_disease": "no"
        }
    }
    response2 = client.post("/api/v1/questionnaire", json=questionnaire2_data)
    assert response2.status_code == 200
    
    # 5) GET patient-status => has_absolute=true and contraindication list includes that item
    status_response2 = client.get("/api/v1/patient-status")
    assert status_response2.status_code == 200
    status_data2 = status_response2.json()
    assert status_data2["has_absolute"] is True
    assert len(status_data2["absolute_contraindications"]) > 0
    
    # Find the metastatic_cancer contraindication
    metastatic_cancer_found = False
    for contra in status_data2["absolute_contraindications"]:
        if contra["id"] == "metastatic_cancer":
            metastatic_cancer_found = True
            assert "metastatic cancer" in contra["question"].lower()
            break
    assert metastatic_cancer_found, "metastatic_cancer contraindication should be in the list"

