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
    
    # Monkey patch for test
    database.save_patient = temp_save_patient
    database.get_patient = temp_get_patient
    database.save_questionnaire = temp_save_questionnaire
    
    yield temp_dir
    
    # Restore original functions
    database.save_patient = original_save_patient
    database.get_patient = original_get_patient
    database.save_questionnaire = original_save_questionnaire
    
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
    client.post("/api/v1/patients", json=patient_data)
    
    # Submit questionnaire
    questionnaire_data = {
        "answers": {
            "metastatic_cancer": "no",
            "decompensated_cirrhosis": "no",
            "severe_lung_disease": "no"
        },
        "results": {
            "hasAbsolute": False,
            "hasRelative": False
        }
    }
    
    response = client.post("/api/v1/questionnaire", json=questionnaire_data)
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["answers"] == questionnaire_data["answers"]
    assert data["results"] == questionnaire_data["results"]
    assert data["id"] is not None
    assert "created_at" in data
    
    # Verify database file was created
    questionnaire_file = Path(temp_data_dir) / "questionnaire.json"
    assert questionnaire_file.exists(), f"Questionnaire file should be created at {questionnaire_file}"
    
    # Verify file contents
    with open(questionnaire_file, 'r') as f:
        saved_data = json.load(f)
        assert len(saved_data) == 1
        assert saved_data[0]["answers"] == questionnaire_data["answers"]
        assert saved_data[0]["id"] == data["id"]


def test_submit_multiple_questionnaires(client, temp_data_dir):
    """Test that multiple questionnaires are appended, not overwritten"""
    # Create patient
    client.post("/api/v1/patients", json={
        "name": "Test",
        "date_of_birth": "1990-01-01"
    })
    
    # Submit first questionnaire
    response1 = client.post("/api/v1/questionnaire", json={
        "answers": {"q1": "yes"},
        "results": {}
    })
    id1 = response1.json()["id"]
    
    # Submit second questionnaire
    response2 = client.post("/api/v1/questionnaire", json={
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


def test_patient_validation(client):
    """Test that patient validation works (required fields)"""
    # Missing required field
    response = client.post("/api/v1/patients", json={
        "date_of_birth": "1990-01-01"
        # Missing name
    })
    assert response.status_code == 422  # Validation error

