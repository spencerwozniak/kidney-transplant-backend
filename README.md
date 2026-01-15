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

### Financial Assessment

- `POST /api/v1/finance/profile` - Create or update financial profile
- `GET /api/v1/finance/profile` - Get financial profile for current patient

### Referral

- `GET /api/v1/referral/centers` - Get list of transplant centers
- `POST /api/v1/referral/state` - Create or update referral state
- `GET /api/v1/referral/state` - Get referral state for current patient

### AI Assistant

- `POST /api/v1/ai-assistant/query` - Query the AI assistant
- `GET /api/v1/ai-assistant/status` - Check AI configuration status
- `GET /api/v1/ai-assistant/context` - Get patient context (debug)

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
│   │   ├── questionnaire.py   # Questionnaire endpoints
│   │   ├── checklist.py        # Checklist endpoints
│   │   ├── status.py           # Patient status endpoints
│   │   ├── finance.py          # Financial assessment endpoints
│   │   ├── referral.py         # Referral endpoints
│   │   ├── ai.py               # AI assistant API endpoints
│   │   ├── middleware.py       # API middleware
│   │   └── utils.py            # API utility functions
│   ├── core/
│   │   └── config.py           # CORS origins configuration
│   ├── database/
│   │   ├── schemas.py          # Pydantic data models (renamed from 'models' to avoid confusion with AI models)
│   │   ├── storage.py          # JSON file read/write functions and data persistence operations
│   │   └── cache.py            # In-memory cache with TTL for storage layer
│   ├── services/
│   │   ├── ai/
│   │   │   ├── config.py       # AI/LLM configuration (API keys, client setup)
│   │   │   ├── service.py      # AI assistant service (prompt building, LLM interaction)
│   │   │   └── image_detection.py  # Image detection and text extraction using OpenAI Vision API
│   │   ├── checklist/
│   │   │   └── initialization.py  # Default checklist creation
│   │   ├── status/
│   │   │   └── computation.py     # Status computation from questionnaire
│   │   └── utils.py                # Utility functions
├── data/                       # Auto-created JSON files (gitignored)
│   ├── patients/               # Per-patient data directories
│   ├── questionnaires/         # Questionnaire submissions
│   ├── checklists/            # Pre-transplant checklists
│   ├── patient_status/        # Computed patient status
│   ├── financial_profiles/    # Financial assessment data
│   ├── patient_referral_states/  # Referral state data
│   ├── documents/             # Uploaded documents
│   ├── patient.json           # Legacy single patient data (deprecated)
│   ├── questionnaire.json     # Legacy questionnaire data (deprecated)
│   ├── checklist.json         # Legacy checklist data (deprecated)
│   ├── patient_status.json    # Legacy status data (deprecated)
│   ├── questions.json         # Question definitions (tracked in git)
│   └── transplant_centers.json  # Transplant center data (tracked in git)
├── tests/                      # Test suite
├── requirements.txt
├── run.py                      # Dev server: uvicorn app.main:app --reload
└── README.md
```

### Directory Organization

The project follows a layered architecture with clear separation of concerns:

- **`app/core/`** - Core infrastructure layer
  - Contains foundational components that the rest of the application depends on
  - `config.py` - Application-wide configuration (CORS, etc.)

- **`app/database/`** - Database layer (data models and storage)
  - Contains both data models (schemas) and storage operations
  - Renamed from `models/` to avoid confusion with AI/LLM models
  - `schemas.py` - All Pydantic models (Patient, QuestionnaireSubmission, etc.)
  - `storage.py` - Data persistence layer (JSON file operations, save/get functions)

- **`app/services/`** - Business logic layer
  - Contains domain-specific business logic organized by feature
  - `ai/` - AI/LLM services (config, service logic)
  - `checklist/` - Checklist-related services
  - `status/` - Status computation services
  - `utils.py` - Shared utility functions for data conversion

- **`app/api/`** - API layer
  - Contains FastAPI route handlers
  - Thin layer that delegates to services and uses database models
  - Routes organized by feature domain (patients, checklist, status, ai, etc.)

This organization ensures:
- **Separation of concerns**: Infrastructure, data models, business logic, and API are clearly separated
- **Dependency direction**: API → Services → Core/Database (clean dependency flow)
- **Clarity**: No confusion between data models and AI models
- **Cohesion**: Related services are grouped into subdirectories (ai/, checklist/, status/)
- **Scalability**: Easy to add new service domains as subdirectories

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
- `finance.py` - Financial assessment endpoints
- `referral.py` - Referral and transplant center endpoints
- `ai.py` - AI assistant endpoints
- `middleware.py` - API middleware
- `utils.py` - API utility functions

**`app/database/storage.py`** - Data storage operations

- `read_json()` / `write_json()` - File I/O helpers
- `save_patient()` / `get_patient()` / `delete_patient()` - Patient operations
- `save_questionnaire()` / `get_questionnaire()` / `get_all_questionnaires_for_patient()` - Questionnaire operations
- `save_checklist()` / `get_checklist()` - Checklist operations
- `save_patient_status()` / `get_patient_status()` - Status operations
- `save_financial_profile()` / `get_financial_profile()` - Financial profile operations
- `save_patient_referral_state()` / `get_patient_referral_state()` - Referral state operations

**`app/database/cache.py`** - In-memory caching layer

- `TTLCache` - Thread-safe in-memory cache with TTL (Time To Live)
- Reduces file I/O for frequently accessed data
- Global cache instances for patient, checklist, status, etc.

**`app/database/schemas.py`** - Pydantic data models

- `Patient` - id, name, date_of_birth, sex, height, weight, email, phone
- `QuestionnaireSubmission` - id, patient_id, answers, submitted_at
- `TransplantChecklist` - id, patient_id, items, created_at, updated_at
- `ChecklistItem` - id, title, description, is_complete, notes, completed_at, order, documents
- `PatientStatus` - id, patient_id, has_absolute, has_relative, absolute_contraindications, relative_contraindications, pathway_stage, updated_at
- `Contraindication` - id, question
- `FinancialProfile` - Financial assessment data
- `PatientReferralState` - Referral status and provider information

**`app/services/ai/config.py`** - AI/LLM configuration

- `get_openai_api_key()` - Retrieves API key from environment
- `get_openai_client()` - Creates configured OpenAI client
- `is_ai_enabled()` - Checks if AI is configured

**`app/services/ai/service.py`** - AI assistant service

- `build_patient_context()` - Aggregates all patient data into structured context
- `format_context_for_prompt()` - Formats context for LLM prompts
- `build_system_prompt()` - Creates system prompt with role and constraints
- `build_user_prompt()` - Combines user query with patient context
- `call_llm()` - Interfaces with LLM providers (OpenAI implemented)
- `get_ai_response()` - Main entry point for getting AI responses

**`app/services/ai/image_detection.py`** - Image processing service

- `encode_image_to_base64()` - Encode image files to base64
- `process_image_with_openai()` - Process images using OpenAI Vision API
- Extracts text from images and scanned PDFs
- Generates descriptions of image content

**`app/api/ai.py`** - AI assistant API endpoints

- `POST /api/v1/ai-assistant/query` - Query the AI assistant
- `GET /api/v1/ai-assistant/status` - Check AI configuration status
- `GET /api/v1/ai-assistant/context` - Get patient context (debug)

**`app/services/checklist/initialization.py`** - Checklist services

- `create_default_checklist()` - Creates default pre-transplant checklist

**`app/services/status/computation.py`** - Status computation services

- `compute_patient_status_from_all_questionnaires()` - Computes status from all questionnaires
- `determine_pathway_stage()` - Determines current pathway stage
- `recompute_pathway_stage()` - Recomputes pathway stage when checklist changes

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

**Per-patient data structure:**
- `data/patients/{patient_id}.json` - Patient data
- `data/questionnaires/{patient_id}.json` - Questionnaire submissions for patient
- `data/checklists/{patient_id}.json` - Pre-transplant checklist for patient
- `data/patient_status/{patient_id}.json` - Computed patient status
- `data/financial_profiles/{patient_id}.json` - Financial assessment data
- `data/patient_referral_states/{patient_id}.json` - Referral state data
- `data/documents/{patient_id}/{item_id}/` - Uploaded documents for checklist items

**Shared data (tracked in git):**
- `data/questions.json` - Question definitions (contains question categories and text)
- `data/transplant_centers.json` - Transplant center data

**Legacy files (deprecated, single-patient mode):**
- `data/patient.json` - Legacy single patient data
- `data/questionnaire.json` - Legacy questionnaire data
- `data/checklist.json` - Legacy checklist data
- `data/patient_status.json` - Legacy status data

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
