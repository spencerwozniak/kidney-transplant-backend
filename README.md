# Kidney Transplant Navigation — Backend

Python FastAPI-based backend for a patient-controlled transplant navigation system.

> **Disclaimer**  
> This project is for educational and informational purposes only and does not provide medical advice.

---

## Current Implementation (MVP)

Minimal backend for demo with single patient support:

- **Patient intake form** - Store basic patient information
- **Eligibility questionnaire** - Store questionnaire answers and compute patient status
- **Pre-transplant checklist** - Track required evaluations and tests
- **Patient status computation** - Automatically compute contraindications from questionnaire
- **JSON file storage** - Simple file-based database (no SQL setup required)

---

## Getting Started

### Prerequisites

- Python 3.9 or higher
- pip (Python package manager)

### Installation

1. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

2. **Run the development server**:

   ```bash
   python run.py
   ```

3. **Access the API**:
   - API: http://localhost:8000
   - Interactive API docs: http://localhost:8000/docs

---

## API Endpoints

### Patients

- `POST /api/v1/patients` - Create/update patient (intake form)
  - Single patient demo: replaces existing if present
  - Automatically creates default checklist for new patient
- `GET /api/v1/patients` - Get current patient
- `DELETE /api/v1/patients` - Delete patient and all associated data

### Questionnaire

- `POST /api/v1/questionnaire` - Submit questionnaire answers
  - Verifies patient exists
  - Automatically computes and saves patient status from answers

### Checklist

- `GET /api/v1/checklist` - Get checklist for current patient
  - Creates default checklist if none exists
- `POST /api/v1/checklist` - Create or update checklist
- `PATCH /api/v1/checklist/items/{item_id}` - Update specific checklist item
  - Update `is_complete`, `completed_at`, and/or `notes`

### Patient Status

- `GET /api/v1/patient-status` - Get computed patient status
  - Returns absolute and relative contraindications based on questionnaire

---

## Tech Stack

- **Python 3.9+**
- **FastAPI** - Modern, fast web framework
- **Pydantic** - Data validation using Python type annotations
- **JSON Database** - Simple file-based storage (easily replaceable with SQL/NoSQL later)
- **Uvicorn** - ASGI server
- REST + JSON
- Simple, auditable business logic

---

## Directory Structure

```
kidney-transplant-backend/
├── app/
│   ├── main.py                 # FastAPI app, CORS, router setup
│   ├── api/
│   │   ├── __init__.py         # Router aggregation
│   │   ├── patients.py         # Patient endpoints
│   │   ├── questionnaire.py    # Questionnaire endpoints
│   │   ├── checklist.py        # Checklist endpoints
│   │   └── status.py           # Patient status endpoints
│   ├── core/
│   │   ├── config.py           # CORS origins configuration
│   │   └── database.py         # JSON file read/write functions
│   ├── models/
│   │   └── schemas.py          # Pydantic models
│   └── services/
│       ├── checklist_initialization.py  # Default checklist creation
│       ├── status_computation.py        # Status computation from questionnaire
│       └── utils.py                     # Utility functions
├── data/                       # Auto-created JSON files (gitignored)
│   ├── patient.json            # Single patient data
│   ├── questionnaire.json      # Questionnaire submissions
│   ├── checklist.json          # Pre-transplant checklist
│   └── patient_status.json     # Computed patient status
├── tests/                      # Test suite
├── requirements.txt
├── run.py                      # Dev server: uvicorn app.main:app --reload
└── README.md
```

### Key Files

**`app/main.py`** - FastAPI application setup

- CORS middleware for mobile app
- Router aggregation mounted at `/api/v1`
- Basic health check endpoint

**`app/api/`** - API endpoints (modular routes)

- `patients.py` - Patient CRUD operations
- `questionnaire.py` - Questionnaire submission and status computation
- `checklist.py` - Checklist management and item updates
- `status.py` - Patient status retrieval

**`app/core/database.py`** - Data storage

- `read_json()` / `write_json()` - File I/O helpers
- `save_patient()` / `get_patient()` / `delete_patient()` - Patient operations
- `save_questionnaire()` - Appends questionnaire submissions
- `save_checklist()` / `get_checklist()` - Checklist operations
- `save_patient_status()` / `get_patient_status()` - Status operations

**`app/models/schemas.py`** - Pydantic models

- `Patient` - id, name, date_of_birth, sex, height, weight, email, phone
- `QuestionnaireSubmission` - id, patient_id, answers, submitted_at
- `TransplantChecklist` - id, patient_id, items, created_at, updated_at
- `ChecklistItem` - id, title, description, is_complete, notes, completed_at, order, documents
- `PatientStatus` - id, patient_id, has_absolute, has_relative, contraindications, updated_at
- `Contraindication` - id, question

**`app/services/`** - Business logic

- `checklist_initialization.py` - Creates default pre-transplant checklist
- `status_computation.py` - Computes patient status from questionnaire answers
- `utils.py` - Helper functions for data conversion

---

## Development

### Running Tests

```bash
python -m pytest tests/
```

Or with verbose output:

```bash
python -m pytest tests/ -v
```

**Note:** On Windows, use `python -m pytest` instead of just `pytest` (ensures it uses the correct Python environment).

Tests verify:

- All API endpoints work correctly
- Database files are created in the correct location (`data/` directory)
- Patient creation and retrieval
- Questionnaire submission and storage
- Error handling (404s, validation errors)

**Note:** Tests use temporary directories to avoid affecting actual data files.

## Data Storage

JSON files in `data/` directory (auto-created, gitignored):

- `patient.json` - Single patient (array with one object, overwritten on save)
- `questionnaire.json` - Array of questionnaire submissions (appended)
- `checklist.json` - Single checklist (array with one object, overwritten on save)
- `patient_status.json` - Single patient status (array with one object, overwritten on save)

**Storage Functions:**

- `save_patient()` / `get_patient()` / `delete_patient()` - Patient operations
- `save_questionnaire()` - Appends to questionnaire array
- `save_checklist()` / `get_checklist()` - Checklist operations
- `save_patient_status()` / `get_patient_status()` - Status operations

**Note:** Single patient assumption simplifies code (no patient_id lookups). Easy to migrate to SQL later by replacing these functions.

## Development Notes

**Current Limitations:**

- Single patient only (no multi-patient support)
- No authentication
- JSON files (not suitable for production concurrency)
- No document upload/storage (checklist items reference documents but don't store them)

---

## Status

MVP for demo/hackathon - minimal implementation to get started. Features will be added incrementally.
