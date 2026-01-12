# Backend Logic Audit Report
## Nexora Kidney Transplant Backend

**Date:** 2026-01-11  
**Auditor:** Backend Logic Auditor  
**Repo:** kidney-transplant-backend

---

## 1. LOGIC MAP

### 1a. Contraindications (Absolute vs Relative)

**Function:** `app/services/status_computation.py::compute_patient_status_from_all_questionnaires()`

**Rule:**
- Load questions from `data/questions.json` via `load_questions()` (returns `[]` if missing - demo-safe)
- Get all questionnaires for patient via `database.get_all_questionnaires_for_patient(patient_id)`
- **Sort questionnaires by `submitted_at` descending** (most recent first) - questionnaires without `submitted_at` are treated as oldest
- Build `latest_answers` dict by processing questionnaires from newest to oldest:
  - For each questionnaire's `answers` dict:
    - For each `question_id` → `answer` pair:
      - Only set if `question_id` not already in `latest_answers` (newest answer wins)
- For each question_id in `latest_answers` where `answer == 'yes'`:
  - Look up question in `questions.json` by `question_id`
  - If `category == 'absolute'` → add to `absolute_contraindications_dict` (deduplicated by `question_id`)
  - If `category == 'relative'` → add to `relative_contraindications_dict` (deduplicated by `question_id`)
- **has_absolute** = `True` if `len(absolute_contraindications) > 0`
- **has_relative** = `True` if `len(relative_contraindications) > 0`

**Key behavior:**
- **Most recent answer wins** - If patient answers "yes" then later answers "no" for same question, the "no" clears the contraindication
- **Deduplication** - same question_id only appears once in lists
- **Empty questions.json** → returns empty contraindication lists (demo-safe, no crash)

**When it runs:**
- `POST /api/v1/questionnaire` → calls `compute_patient_status_from_all_questionnaires()` after saving (line 57)
- `GET /api/v1/patient-status` → calls `compute_patient_status_from_all_questionnaires()` on every request (line 30)

**Inputs:**
- `patient_id: str` - Patient ID to compute status for
- Reads: `data/questionnaire.json` (all questionnaires), `data/questions.json` (question definitions)

**Outputs:**
- `PatientStatus` object with:
  - `has_absolute: bool`
  - `has_relative: bool`
  - `absolute_contraindications: List[Contraindication]` (deduplicated)
  - `relative_contraindications: List[Contraindication]` (deduplicated)
  - `pathway_stage: str` (computed via `determine_pathway_stage()`)

---

### 1b. Patient Status Roll-up Across Multiple Questionnaires

**Function:** `app/services/status_computation.py::compute_patient_status_from_all_questionnaires()`

**Rule:**
1. Get all questionnaires for patient via `database.get_all_questionnaires_for_patient(patient_id)`
2. If no questionnaires → raise `ValueError` (caught by endpoint, returns 404)
3. **Sort questionnaires by `submitted_at` descending** (most recent first) - missing `submitted_at` treated as oldest
4. Build `latest_answers` dict by processing questionnaires from newest to oldest:
   - For each questionnaire's `answers` dict:
     - For each `question_id` → `answer` pair:
       - Only add to `latest_answers` if `question_id` not already present (newest wins)
5. Process `latest_answers` (only 'yes' answers create contraindications):
   - For each `question_id` where `answer == 'yes'`:
     - Check if question exists in `questions.json`
     - If category='absolute' → add to absolute dict (deduplicated by question_id)
     - If category='relative' → add to relative dict (deduplicated by question_id)
6. **Most recent answer wins:** Later "no" answers override earlier "yes" answers
7. **Deduplication:** Same question_id only counted once (most recent answer used)

**When it runs:**
- `POST /api/v1/questionnaire` (line 57) - after saving new questionnaire
- `GET /api/v1/patient-status` (line 30) - on every GET request

**Inputs:**
- `patient_id: str`
- Reads: `data/questionnaire.json`, `data/questions.json`

**Outputs:**
- `PatientStatus` with aggregated contraindications (based on most recent answers)

**Example:**
- Questionnaire 1 (older): `metastatic_cancer: "yes"` → would add contraindication
- Questionnaire 2 (newer): `metastatic_cancer: "no"` → clears contraindication
- Result: `has_absolute=False`, no contraindications (most recent answer wins)

---

### 1c. Pathway Stage Selection

**Function:** `app/services/status_computation.py::determine_pathway_stage()`

**Decision Tree (in order):**

```
1. IF patient exists AND patient.has_ckd_esrd == False:
   → return 'identification'

2. IF has_referral == True AND has_questionnaire == False:
   → return 'evaluation' (has referral but no questionnaire yet)

3. IF has_questionnaire == False:
   → return 'identification'

4. IF has_referral is not True (False or None):
   → return 'referral' (need referral to advance)

5. IF has_questionnaire == True AND checklist == None:
   → return 'referral'

6. IF checklist exists:
   a. Get items = checklist.get('items', []) or [] (guard against None)
   b. IF items is empty:
      → return 'referral'
   c. Calculate: completion_percentage = completed_items / total_items (0 if total_items == 0)
   d. IF completion_percentage < 0.8:
      → return 'evaluation'
   e. IF completion_percentage >= 0.8:
      → return 'selection'

7. DEFAULT (has_questionnaire == True, checklist exists but logic didn't match):
   → return 'referral'
```

**When it runs:**
- Called by `compute_patient_status_from_all_questionnaires()` (line 215)
- Called by `recompute_pathway_stage()` (line 250) - when checklist changes
- Called by `compute_patient_status()` (line 135) - legacy function

**Inputs:**
- `has_questionnaire: bool` - whether patient has completed questionnaire
- `checklist: Optional[Dict]` - checklist data (from `database.get_checklist()`)
- `patient: Optional[Dict]` - patient data (from `database.get_patient()`)

**Outputs:**
- `str` - one of: `'identification'`, `'referral'`, `'evaluation'`, `'selection'`

**Key thresholds:**
- **80% completion** = threshold between 'evaluation' and 'selection'
- **has_referral is not True** (False or None) → always 'referral' (even if checklist complete)
- **No checklist** → always 'referral' (even if questionnaire exists)
- **has_referral=True + no questionnaire** → 'evaluation' (special case: referral exists but questionnaire not completed)
- **checklist.items=None guard** → treated as empty list (line 84: `items = items or []`)

---

### 1d. Checklist Completion Logic

**Function:** `app/services/status_computation.py::determine_pathway_stage()` (lines 82-99)

**Rule:**
- Get `checklist.items` with guard: `items = checklist.get('items', []) or []` (line 83-84)
- Count: `completed_items = sum(1 for item in items if item.get('is_complete', False))` (line 88)
- Count: `total_items = len(items)` (line 89)
- Calculate: `completion_percentage = completed_items / total_items if total_items > 0 else 0` (line 90)
- **If < 80%:** → `'evaluation'` (line 93)
- **If >= 80%:** → `'selection'` (line 98)

**When it runs:**
- Every time `determine_pathway_stage()` is called (which happens on status computation)

**Inputs:**
- `checklist: Optional[Dict]` with `items: List[ChecklistItem]`
- Each item has `is_complete: bool`

**Outputs:**
- Affects `pathway_stage` in PatientStatus

**Checklist update triggers:**
- `PATCH /api/v1/checklist/items/{item_id}` (lines 129-135) - updates item, then calls `recompute_pathway_stage()`
- `POST /api/v1/checklist/items/{item_id}/documents` (lines 219-225) - uploads document, then calls `recompute_pathway_stage()`

**Checklist creation:**
- `POST /api/v1/patients` (lines 27-34) - automatically creates default checklist with 6 items
- `GET /api/v1/checklist` (lines 30-46) - auto-creates default checklist if none exists (only if patient exists)

---

## 2. DATA FLOW DIAGRAM

### 2a. Create Patient

```
Frontend: POST /api/v1/patients
  ↓
app/api/patients.py::create_patient()
  ↓
1. Generate UUID for patient.id (line 23)
2. database.save_patient() → writes data/patient.json (line 24)
3. create_default_checklist(patient.id) → creates 6 default items (line 27)
4. Generate UUID for checklist.id (line 28)
5. database.save_checklist() → writes data/checklist.json (line 34)
  ↓
Response: Patient object (with id)
```

**Files touched:**
- `data/patient.json` (created/overwritten)
- `data/checklist.json` (created/overwritten - default checklist with 6 items)

---

### 2b. Submit Questionnaire

```
Frontend: POST /api/v1/questionnaire
  ↓
app/api/questionnaire.py::submit_questionnaire()
  ↓
1. Verify patient exists (database.get_patient()) (line 38)
2. Verify patient_id matches current patient (line 43-44)
3. Generate UUID for submission.id if not provided (line 47-48)
4. Convert datetime fields to ISO strings (line 51)
5. database.save_questionnaire() → APPENDS to data/questionnaire.json (line 54)
6. compute_patient_status_from_all_questionnaires(patient_id):
   a. database.get_all_questionnaires_for_patient() → reads data/questionnaire.json
   b. Sort questionnaires by submitted_at descending (most recent first)
   c. Build latest_answers dict (newest answer wins per question_id)
   d. load_questions() → reads data/questions.json
   e. Process latest_answers → compute contraindications (only 'yes' answers)
   f. determine_pathway_stage() → reads data/checklist.json, data/patient.json
   g. Returns PatientStatus
7. Generate UUID for status.id (line 58)
8. Convert datetime fields to ISO strings (line 61)
9. database.save_patient_status() → OVERWRITES data/patient_status.json (line 64)
  ↓
Response: QuestionnaireSubmission object
```

**Files touched:**
- `data/questionnaire.json` (appended)
- `data/patient_status.json` (overwritten)
- **Reads:** `data/questions.json`, `data/checklist.json`, `data/patient.json`

---

### 2c. Fetch Patient Status

```
Frontend: GET /api/v1/patient-status
  ↓
app/api/status.py::get_patient_status()
  ↓
1. database.get_patient() → reads data/patient.json (line 22)
2. If no patient → HTTP 404 (line 23-24)
3. compute_patient_status_from_all_questionnaires(patient_id):
   a. database.get_all_questionnaires_for_patient() → reads data/questionnaire.json
   b. Sort questionnaires by submitted_at descending (most recent first)
   c. Build latest_answers dict (newest answer wins per question_id)
   d. load_questions() → reads data/questions.json
   e. Process latest_answers → compute contraindications (only 'yes' answers)
   f. determine_pathway_stage() → reads data/checklist.json, data/patient.json
   g. Returns PatientStatus
4. If ValueError (no questionnaires) → HTTP 404 (line 31-33)
5. Generate UUID if status.id missing (line 37-38)
6. Convert datetime fields to ISO strings (line 41)
7. database.save_patient_status() → OVERWRITES data/patient_status.json (line 42)
  ↓
Response: PatientStatus object
```

**Files touched:**
- `data/patient_status.json` (overwritten)
- **Reads:** `data/patient.json`, `data/questionnaire.json`, `data/questions.json`, `data/checklist.json`

---

### 2d. Checklist Update

```
Frontend: PATCH /api/v1/checklist/items/{item_id}
  ↓
app/api/checklist.py::update_checklist_item()
  ↓
1. Verify patient exists (line 92-94)
2. database.get_checklist() → reads data/checklist.json (line 97)
3. If no checklist → HTTP 404 (line 98-99)
4. Find item by item_id (line 103-118)
5. Update item fields:
   - is_complete (if False, clears completed_at)
   - completed_at
   - notes (None if empty string)
   - documents
6. Update checklist.updated_at timestamp (line 124)
7. database.save_checklist() → OVERWRITES data/checklist.json (line 127)
8. If patient_status exists:
   a. database.get_patient_status() → reads data/patient_status.json (line 130)
   b. Create PatientStatus object from data (line 132)
   c. recompute_pathway_stage() → reads data/checklist.json, data/patient.json (line 133)
   d. Convert datetime fields to ISO strings (line 134)
   e. database.save_patient_status() → OVERWRITES data/patient_status.json (line 135)
  ↓
Response: TransplantChecklist object
```

**Files touched:**
- `data/checklist.json` (overwritten)
- `data/patient_status.json` (overwritten if status exists)
- **Reads:** `data/patient.json`

---

### 2e. Document Upload

```
Frontend: POST /api/v1/checklist/items/{item_id}/documents
  ↓
app/api/checklist.py::upload_checklist_item_document()
  ↓
1. Verify patient exists
2. database.get_checklist() → reads data/checklist.json
3. Find item by item_id
4. Validate file type (PDF, images)
5. Create directory: data/documents/{patient_id}/{item_id}/
6. Save file with timestamp prefix
7. Append relative path to item.documents array
8. database.save_checklist() → OVERWRITES data/checklist.json
9. If patient_status exists:
   a. recompute_pathway_stage() → updates pathway_stage
   b. database.save_patient_status() → OVERWRITES data/patient_status.json
  ↓
Response: TransplantChecklist object
```

**Files touched:**
- `data/documents/{patient_id}/{item_id}/{filename}` (created)
- `data/checklist.json` (overwritten)
- `data/patient_status.json` (overwritten if status exists)

---

### 2f. Delete Patient

```
Frontend: DELETE /api/v1/patients
  ↓
app/api/patients.py::delete_patient()
  ↓
1. Verify patient exists (returns 404 if not)
2. database.delete_patient():
   a. Get patient_id before deletion
   b. Delete: data/patient.json
   c. Delete: data/questionnaire.json
   d. Delete: data/checklist.json
   e. Delete: data/patient_status.json
   f. Delete: data/financial_profile.json
   g. Delete: data/patient_referral_state.json
   h. Delete: data/documents/{patient_id}/ (entire directory)
  ↓
Response: {"message": "Patient deleted successfully"}
```

**Files deleted:**
- All runtime data files (except `data/questions.json`)

---

## 3. CORRECTNESS + EDGE CASES

### Edge Case Analysis

| # | Edge Case | Current Handling | Severity | Proposed Fix |
|---|-----------|------------------|----------|--------------|
| 1 | **missing questions.json** | ✅ Returns `[]`, no crash. Status computed with empty contraindications. | Minor | None needed - already demo-safe |
| 2 | **multiple questionnaires with conflicting answers** | ✅ **FIXED:** Rollup logic sorts by submitted_at descending, uses most recent answer per question_id. Later "no" clears earlier "yes". | None | Already fixed |
| 3 | **delete patient when no patient exists** | ✅ Returns 404 (fixed) | None | Already fixed |
| 4 | **checklist exists without patient** | ✅ GET /checklist checks for patient first (line 33-34), returns 404 if no patient. Auto-create only happens if patient exists. | None | Already handled correctly |
| 5 | **document upload without checklist** | ✅ Returns 404 "No checklist found" | None | Already handled |
| 6 | **patient-status called before questionnaire** | ✅ Returns 404 "No questionnaires found" | None | Already handled |
| 7 | **patient-status called with patient but no questionnaires** | ✅ Returns 404 (ValueError caught) | None | Already handled |
| 8 | **checklist completion exactly 80%** | ✅ Returns 'selection' (>= 0.8) | None | Correct behavior |
| 9 | **checklist with 0 items** | ✅ Returns 'referral' (line 76-77) | None | Correct behavior |
| 10 | **has_referral=None vs has_referral=False** | ✅ **FIXED:** Code checks `has_referral is not True` (line 73), so both `False` and `None` return 'referral'. Only explicit `True` advances past referral. | None | Already fixed |
| 11 | **questionnaire with unknown question_id** | ✅ Ignored (question_map.get() returns None) | Minor | None needed - graceful degradation |
| 12 | **empty answers dict in questionnaire** | ✅ No contraindications found (loop doesn't execute) | None | Correct behavior |
| 13 | **checklist.items is None (not empty list)** | ✅ **FIXED:** Code has `items = items or []` guard on line 84, preventing crash if items is None. | None | Already fixed |
| 14 | **pathway_stage computed when patient deleted mid-request** | ⚠️ Race condition: patient deleted between get_patient() and status computation. | Minor | Low risk in single-user demo |
| 15 | **questions.json has invalid JSON** | ✅ Returns `[]`, no crash | None | Already demo-safe |

---

## 4. "IS IT THE BEST LOGIC?" - Clinical Realism Evaluation

### Current Pathway Stage Logic Status:

**Issue 1: has_referral=None ambiguity** ✅ **FIXED**
- Current: `has_referral is not True` (line 73) → 'referral' for both False and None
- **Status:** Correctly requires explicit `has_referral=True` to advance past referral stage

**Issue 2: Checklist auto-creation on GET**
- Current: GET /checklist creates default checklist if none exists (only if patient exists)
- **Status:** Still auto-creates regardless of questionnaire status, but this is acceptable for demo flow

**Issue 3: Pathway stage jumps**
- Current: Special case: `has_referral=True + no questionnaire` → 'evaluation' (line 63-64)
- **Status:** This allows evaluation stage before questionnaire, which may be intentional for demo

**Issue 4: 80% threshold is arbitrary**
- Current: Hard-coded 0.8 threshold (line 93)
- **Status:** Documented as demo threshold - acceptable for MVP

**Issue 5: Multiple questionnaires with conflicting answers** ✅ **FIXED**
- Current: Sorts by submitted_at descending, uses most recent answer per question_id
- **Status:** Later "no" answers correctly clear earlier "yes" answers

### Implementation Status:

#### ✅ Already Fixed (No Action Needed):

1. **has_referral=None ambiguity** ✅
   - File: `app/services/status_computation.py::determine_pathway_stage()` (line 73)
   - Status: Code correctly checks `has_referral is not True` (handles both False and None)

2. **checklist.items=None crash risk** ✅
   - File: `app/services/status_computation.py::determine_pathway_stage()` (line 84)
   - Status: Code has `items = items or []` guard

3. **Conflicting questionnaire answers** ✅
   - File: `app/services/status_computation.py::compute_patient_status_from_all_questionnaires()` (lines 180-203)
   - Status: Code sorts by submitted_at descending and uses most recent answer per question_id

#### Optional Improvements (Low Priority):

4. **Checklist auto-creation timing**
   - File: `app/api/checklist.py::get_checklist()` (line 30-46)
   - Current: Auto-creates if patient exists (regardless of questionnaire)
   - Optional: Only auto-create if questionnaire exists
   - Impact: Minor - current behavior acceptable for demo

#### Not Recommended:

5. **Add "transplantation" and "post-transplant" stages**
   - Not needed for demo - current stages sufficient

6. **Add time-based pathway progression**
   - Too complex for demo, adds unnecessary logic

---

## 5. DEMO-SAFETY VERIFICATION PLAN

### Happy Path (Full Demo Run):

```bash
# 1. Create patient
curl -X POST http://127.0.0.1:8000/api/v1/patients \
  -H "Content-Type: application/json" \
  -d '{"name":"Demo Patient","date_of_birth":"1980-01-01"}'
# Expected: HTTP 200, Patient object with id

# 2. Submit questionnaire (no contraindications)
curl -X POST http://127.0.0.1:8000/api/v1/questionnaire \
  -H "Content-Type: application/json" \
  -d '{"patient_id":"<PATIENT_ID>","answers":{"metastatic_cancer":"no","decompensated_cirrhosis":"no"}}'
# Expected: HTTP 200, QuestionnaireSubmission

# 3. Get patient status
curl http://127.0.0.1:8000/api/v1/patient-status
# Expected: HTTP 200, has_absolute=false, has_relative=false, pathway_stage="referral"

# 4. Submit second questionnaire (with absolute contraindication)
curl -X POST http://127.0.0.1:8000/api/v1/questionnaire \
  -H "Content-Type: application/json" \
  -d '{"patient_id":"<PATIENT_ID>","answers":{"metastatic_cancer":"yes"}}'
# Expected: HTTP 200

# 5. Get patient status (should show absolute contraindication)
curl http://127.0.0.1:8000/api/v1/patient-status
# Expected: HTTP 200, has_absolute=true, pathway_stage="referral"

# 6. Submit third questionnaire (clearing the contraindication)
curl -X POST http://127.0.0.1:8000/api/v1/questionnaire \
  -H "Content-Type: application/json" \
  -d '{"patient_id":"<PATIENT_ID>","answers":{"metastatic_cancer":"no"}}'
# Expected: HTTP 200

# 7. Get patient status (contraindication should be cleared - most recent answer wins)
curl http://127.0.0.1:8000/api/v1/patient-status
# Expected: HTTP 200, has_absolute=false (most recent "no" cleared earlier "yes")

# 8. Update checklist item
curl -X PATCH http://127.0.0.1:8000/api/v1/checklist/items/physical_exam \
  -H "Content-Type: application/json" \
  -d '{"is_complete":true}'
# Expected: HTTP 200, Checklist with updated item

# 9. Get patient status (pathway_stage may change)
curl http://127.0.0.1:8000/api/v1/patient-status
# Expected: HTTP 200, pathway_stage="evaluation" or "selection" depending on completion
```

### Failure Case 1: Missing questions.json

```bash
# Remove questions.json temporarily
mv data/questions.json data/questions.json.bak

# Submit questionnaire
curl -X POST http://127.0.0.1:8000/api/v1/questionnaire \
  -H "Content-Type: application/json" \
  -d '{"patient_id":"<PATIENT_ID>","answers":{"metastatic_cancer":"yes"}}'
# Expected: HTTP 200 (no crash)

# Get patient status
curl http://127.0.0.1:8000/api/v1/patient-status
# Expected: HTTP 200, has_absolute=false (no questions to map), pathway_stage computed

# Restore
mv data/questions.json.bak data/questions.json
```

### Failure Case 2: Patient deleted mid-flow

```bash
# Create patient and questionnaire
curl -X POST http://127.0.0.1:8000/api/v1/patients ...
curl -X POST http://127.0.0.1:8000/api/v1/questionnaire ...

# Delete patient
curl -X DELETE http://127.0.0.1:8000/api/v1/patients
# Expected: HTTP 200

# Try to get patient status
curl http://127.0.0.1:8000/api/v1/patient-status
# Expected: HTTP 404 "Patient not found" (not 500)

# Try to get questionnaire
curl http://127.0.0.1:8000/api/v1/questionnaire
# Expected: HTTP 404 "Questionnaire not found" (not 500)
```

### Verification Checklist:

- [x] No endpoint returns HTTP 500 in happy path
- [x] No endpoint returns HTTP 500 when questions.json missing
- [x] No endpoint returns HTTP 500 when patient deleted
- [x] All endpoints return deterministic responses
- [x] Pathway stage logic is consistent
- [x] Contraindication rollup works across multiple questionnaires

---

## SUMMARY OF FINDINGS

### Strengths:
1. ✅ Demo-safe fallbacks (questions.json missing → empty list)
2. ✅ Deterministic pathway stage logic
3. ✅ Proper error handling (404s, not 500s)
4. ✅ Rollup logic correctly aggregates across questionnaires using most recent answers
5. ✅ Most recent answer wins - later "no" clears earlier "yes" contraindications
6. ✅ Proper has_referral handling - requires explicit True to advance
7. ✅ Checklist items=None guard prevents crashes

### Critical Issues Status:
1. ✅ **FIXED:** Conflicting questionnaire answers - Now uses most recent answer per question_id
2. ✅ **FIXED:** has_referral=None ambiguity - Now correctly checks `is not True`
3. ✅ **FIXED:** checklist.items=None crash risk - Now has guard clause

### Current Implementation Notes:
- Questionnaire rollup uses most recent answer (sorted by submitted_at descending)
- Pathway stage logic properly handles has_referral=None vs False vs True
- Checklist completion threshold is 80% (hard-coded for demo)
- Checklist auto-creates on patient creation and on GET if missing (acceptable for demo)

---

**End of Audit Report**
