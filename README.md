# Kidney Transplant Navigation — Backend

Python FastAPI-based backend for a patient-controlled transplant navigation system.

> **Disclaimer**  
> This project is for educational and informational purposes only and does not provide medical advice.

---

## Current Implementation (MVP)

Minimal backend for demo with single patient support:

- **Patient intake form** - Store basic patient information
- **Eligibility questionnaire** - Store questionnaire answers and results
- **JSON file storage** - Simple file-based database (no SQL setup required)

---

## API Endpoints

### Patients

- `POST /api/v1/patients` - Create/update patient (intake form)
  - Single patient demo: replaces existing if present
- `GET /api/v1/patients` - Get current patient

### Questionnaire

- `POST /api/v1/questionnaire` - Submit questionnaire answers and results

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
│   │   └── routes.py           # 3 endpoints: POST/GET patients, POST questionnaire
│   ├── core/
│   │   ├── config.py           # CORS origins configuration
│   │   └── database.py          # JSON file read/write functions
│   └── models/
│       └── schemas.py          # Patient, QuestionnaireSubmission models
├── data/                       # Auto-created JSON files (gitignored)
│   ├── patient.json          # Single patient data
│   └── questionnaire.json     # Questionnaire submissions
├── requirements.txt
├── run.py                      # Dev server: uvicorn app.main:app --reload
└── README.md
```

### Key Files

**`app/main.py`** - FastAPI application setup

- CORS middleware for mobile app
- Single router mounted at `/api/v1`
- Basic health check endpoint

**`app/api/routes.py`** - API endpoints

- `POST /patients` - Save patient (generates UUID, overwrites existing)
- `GET /patients` - Get single patient (no ID needed)
- `POST /questionnaire` - Save questionnaire (verifies patient exists first)

**`app/core/database.py`** - Data storage

- `read_json()` / `write_json()` - File I/O helpers
- `save_patient()` - Overwrites `data/patient.json` (single patient)
- `get_patient()` - Returns first patient from file
- `save_questionnaire()` - Appends to `data/questionnaire.json`

**`app/models/schemas.py`** - Pydantic models

- `Patient` - id, name, date_of_birth, email, phone
- `QuestionnaireSubmission` - answers (dict), results (optional dict)

---

## Getting Started

### Prerequisites

- Python 3.9 or higher
- pip (Python package manager)

### Installation

1. **Create a virtual environment** (recommended):

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Run the development server**:

   ```bash
   python run.py
   ```

   Or using uvicorn directly:

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Access the API**:
   - API: http://localhost:8000
   - Interactive API docs: http://localhost:8000/docs
   - Alternative docs: http://localhost:8000/redoc

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

**Storage Functions:**

- `save_patient()` - Writes single patient, overwrites file
- `get_patient()` - Reads first patient from file
- `save_questionnaire()` - Appends to questionnaire array

**Note:** Single patient assumption simplifies code (no patient_id lookups). Easy to migrate to SQL later by replacing these functions.

## Development Notes

**Current Limitations:**

- Single patient only (no multi-patient support)
- No authentication
- No service layer (routes call database directly)
- JSON files (not suitable for production concurrency)

**Adding Features:**

1. Add Pydantic model in `app/models/schemas.py`
2. Add storage function in `app/core/database.py`
3. Add route in `app/api/routes.py`

---

## Status

MVP for demo/hackathon - minimal implementation to get started. Features will be added incrementally.
