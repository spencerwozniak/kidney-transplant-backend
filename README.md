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
  - Automatically computes and saves patient status from all questionnaires
  - Supports multiple questionnaire submissions (latest answer wins per question)
- `GET /api/v1/questionnaire` - Get most recent questionnaire for current patient

### Checklist

- `GET /api/v1/checklist` - Get checklist for current patient
  - Creates default checklist if none exists
- `POST /api/v1/checklist` - Create or update checklist
- `PATCH /api/v1/checklist/items/{item_id}` - Update specific checklist item
  - Update `is_complete`, `completed_at`, and/or `notes`
  - Automatically recomputes pathway stage when checklist changes
- `POST /api/v1/checklist/items/{item_id}/documents` - Upload document for checklist item
- `GET /api/v1/documents/{file_path}` - Retrieve uploaded document

### Patient Status

- `GET /api/v1/patient-status` - Get computed patient status
  - Returns absolute and relative contraindications based on all questionnaires
  - Uses latest answer per question (latest submission wins)
  - Returns current pathway stage based on patient data and checklist completion

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
- `PatientStatus` - id, patient_id, has_absolute, has_relative, absolute_contraindications, relative_contraindications, pathway_stage, updated_at
- `Contraindication` - id, question

**`app/services/`** - Business logic

- `checklist_initialization.py` - Creates default pre-transplant checklist
- `status_computation.py` - Computes patient status from questionnaire answers
  - Rolls up all questionnaires for a patient (latest answer wins)
  - Determines pathway stage based on questionnaire, referral status, and checklist completion
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
- Patient status rollup across multiple questionnaires (latest answer wins)
- Pathway stage determination (has_referral logic)
- Error handling (404s, validation errors)

**Note:** Tests use temporary directories to avoid affecting actual data files.

## Business Logic

### Patient Status Computation

Patient status is computed by rolling up all questionnaires for a patient:

- **Latest Answer Wins**: For each question, the most recent answer (by `submitted_at`) is used
  - If a patient answers "yes" to a question, then later answers "no", the "no" takes precedence
  - Questionnaires without `submitted_at` are treated as oldest (sorted last)
- **Contraindications**: Only "yes" answers from the latest submissions create contraindications
  - Absolute contraindications: Questions with `category="absolute"` in `data/questions.json`
  - Relative contraindications: Questions with `category="relative"` in `data/questions.json`
- **Deduplication**: Each question_id appears at most once in contraindication lists

### Pathway Stage Determination

Pathway stages progress based on patient data:

1. **identification** - Patient exists but:
   - No questionnaire completed, OR
   - `has_ckd_esrd` is explicitly `False`

2. **referral** - Questionnaire completed but:
   - `has_referral` is not explicitly `True` (None or False), OR
   - No checklist exists, OR
   - Checklist exists but has no items

3. **evaluation** - Checklist exists, has items, and:
   - `has_referral` is explicitly `True`
   - Less than 80% of checklist items are complete

4. **selection** - Checklist exists, has items, and:
   - `has_referral` is explicitly `True`
   - 80% or more of checklist items are complete

**Note:** Pathway stage is automatically recomputed when:
- A questionnaire is submitted
- A checklist item is updated
- A document is uploaded

## Data Storage

JSON files in `data/` directory (auto-created, gitignored):

- `patient.json` - Single patient (array with one object, overwritten on save)
- `questionnaire.json` - Array of questionnaire submissions (appended, all submissions retained)
- `checklist.json` - Single checklist (array with one object, overwritten on save)
- `patient_status.json` - Single patient status (array with one object, overwritten on save)
- `questions.json` - Question definitions (tracked in git, contains question categories and text)
- `data/documents/{patient_id}/{item_id}/` - Uploaded documents for checklist items

**Storage Functions:**

- `save_patient()` / `get_patient()` / `delete_patient()` - Patient operations
- `save_questionnaire()` - Appends to questionnaire array (all submissions retained)
- `get_all_questionnaires_for_patient()` - Gets all questionnaires for a patient
- `save_checklist()` / `get_checklist()` - Checklist operations
- `save_patient_status()` / `get_patient_status()` - Status operations

**Note:** Single patient assumption simplifies code (no patient_id lookups). Easy to migrate to SQL later by replacing these functions.

## Development Notes

**Current Limitations:**

- Single patient only (no multi-patient support)
- No authentication
- JSON files (not suitable for production concurrency)
- Document storage is file-based (documents stored in `data/documents/` directory)

**Demo-Safe Features:**

- Missing `data/questions.json` returns empty contraindications (no 500 errors)
- Handles missing submitted_at timestamps gracefully
- Robust error handling for missing data files

---

## Status

MVP for demo/hackathon - minimal implementation to get started. Features will be added incrementally.
