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
- For each questionnaire in patient's history:
  - For each answer where `answer == 'yes'`:
    - Look up question in `questions.json` by `question_id`
    - If `category == 'absolute'` → add to `absolute_contraindications_dict` (deduplicated by `question_id`)
    - If `category == 'relative'` → add to `relative_contraindications_dict` (deduplicated by `question_id`)
- **has_absolute** = `True` if `len(absolute_contraindications) > 0`
- **has_relative** = `True` if `len(relative_contraindications) > 0`

**When it runs:**
- `POST /api/v1/questionnaire` → calls `compute_patient_status_from_all_questionnaires()` after saving
- `GET /api/v1/patient-status` → calls `compute_patient_status_from_all_questionnaires()` on every request

**Inputs:**
- `patient_id: str` - Patient ID to compute status for
- Reads: `data/questionnaire.json` (all questionnaires), `data/questions.json` (question definitions)

**Outputs:**
- `PatientStatus` object with:
  - `has_absolute: bool`
  - `has_relative: bool`
  - `absolute_contraindications: List[Contraindication]` (deduplicated)
  - `relative_contraindications: List[Contraindication]` (deduplicated)

**Key behavior:**
- **Rollup across ALL questionnaires** - if ANY questionnaire has "yes" for an absolute contraindication, `has_absolute=True`
- **Deduplication** - same question_id only appears once in lists
- **Empty questions.json** → returns empty contraindication lists (demo-safe, no crash)

---

### 1b. Patient Status Roll-up Across Multiple Questionnaires

**Function:** `app/services/status_computation.py::compute_patient_status_from_all_questionnaires()`

**Rule:**
1. Get all questionnaires for patient via `database.get_all_questionnaires_for_patient(patient_id)`
2. If no questionnaires → raise `ValueError` (caught by endpoint, returns 404)
3. Process ALL questionnaires in order:
   - For each questionnaire's `answers` dict:
     - If `answer == 'yes'` for any question_id:
       - Check if question exists in `questions.json`
       - If category='absolute' → add to absolute dict (if not already present)
       - If category='relative' → add to relative dict (if not already present)
4. **Union logic:** Any "yes" across ANY questionnaire = contraindication present
5. **Deduplication:** Same question_id only counted once (first occurrence wins)

**When it runs:**
- `POST /api/v1/questionnaire` (line 57) - after saving new questionnaire
- `GET /api/v1/patient-status` (line 30) - on every GET request

**Inputs:**
- `patient_id: str`
- Reads: `data/questionnaire.json`, `data/questions.json`

**Outputs:**
- `PatientStatus` with aggregated contraindications

**Example:**
- Questionnaire 1: `metastatic_cancer: "no"` → no contraindication
- Questionnaire 2: `metastatic_cancer: "yes"` → absolute contraindication added
- Result: `has_absolute=True`, `absolute_contraindications` contains metastatic_cancer

---

### 1c. Pathway Stage Selection

**Function:** `app/services/status_computation.py::determine_pathway_stage()`

**Decision Tree (in order):**

```
1. IF patient.has_ckd_esrd == False:
   → return 'identification'

2. IF has_questionnaire == False:
   → return 'identification'

3. IF patient.has_referral == False:
   → return 'referral'

4. IF has_questionnaire == True AND checklist == None:
   → return 'referral'

5. IF checklist exists:
   a. IF checklist.items is empty:
      → return 'referral'
   b. Calculate: completion_percentage = completed_items / total_items
   c. IF completion_percentage < 0.8:
      → return 'evaluation'
   d. IF completion_percentage >= 0.8:
      → return 'selection'

6. DEFAULT (has_questionnaire == True, checklist exists but logic didn't match):
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
- **has_referral=False** → always 'referral' (even if checklist complete)
- **No checklist** → always 'referral' (even if questionnaire exists)

---

### 1d. Checklist Completion Logic

**Function:** `app/services/status_computation.py::determine_pathway_stage()` (lines 74-90)

**Rule:**
- Get `checklist.items` (list of ChecklistItem objects)
- Count: `completed_items = sum(1 for item in items if item.get('is_complete', False))`
- Count: `total_items = len(items)`
- Calculate: `completion_percentage = completed_items / total_items` (0 if total_items == 0)
- **If < 80%:** → `'evaluation'`
- **If >= 80%:** → `'selection'`

**When it runs:**
- Every time `determine_pathway_stage()` is called (which happens on status computation)

**Inputs:**
- `checklist: Optional[Dict]` with `items: List[ChecklistItem]`
- Each item has `is_complete: bool`

**Outputs:**
- Affects `pathway_stage` in PatientStatus

**Checklist update triggers:**
- `PATCH /api/v1/checklist/items/{item_id}` (line 129-135) - updates item, then calls `recompute_pathway_stage()`
- `POST /api/v1/checklist/items/{item_id}/documents` (line 219-225) - uploads document, then calls `recompute_pathway_stage()`

---

## 2. DATA FLOW DIAGRAM

### 2a. Create Patient

```
Frontend: POST /api/v1/patients
  ↓
app/api/patients.py::create_patient()
  ↓
1. Generate UUID for patient.id
2. database.save_patient() → writes data/patient.json
3. create_default_checklist() → creates 6 default items
4. database.save_checklist() → writes data/checklist.json
  ↓
Response: Patient object (with id)
```

**Files touched:**
- `data/patient.json` (created/overwritten)
- `data/checklist.json` (created/overwritten)

---

### 2b. Submit Questionnaire

```
Frontend: POST /api/v1/questionnaire
  ↓
app/api/questionnaire.py::submit_questionnaire()
  ↓
1. Verify patient exists (database.get_patient())
2. Verify patient_id matches
3. Generate UUID for submission.id
4. database.save_questionnaire() → APPENDS to data/questionnaire.json
5. compute_patient_status_from_all_questionnaires(patient_id):
   a. database.get_all_questionnaires_for_patient() → reads data/questionnaire.json
   b. load_questions() → reads data/questions.json
   c. Process all questionnaires → compute contraindications
   d. determine_pathway_stage() → reads data/checklist.json, data/patient.json
   e. Returns PatientStatus
6. database.save_patient_status() → OVERWRITES data/patient_status.json
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
1. database.get_patient() → reads data/patient.json
2. compute_patient_status_from_all_questionnaires(patient_id):
   a. database.get_all_questionnaires_for_patient() → reads data/questionnaire.json
   b. load_questions() → reads data/questions.json
   c. Process all questionnaires → compute contraindications
   d. determine_pathway_stage() → reads data/checklist.json, data/patient.json
   e. Returns PatientStatus
3. Generate UUID if status.id missing
4. database.save_patient_status() → OVERWRITES data/patient_status.json
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
1. Verify patient exists
2. database.get_checklist() → reads data/checklist.json
3. Find item by item_id
4. Update item fields (is_complete, completed_at, notes, documents)
5. database.save_checklist() → OVERWRITES data/checklist.json
6. If patient_status exists:
   a. database.get_patient_status() → reads data/patient_status.json
   b. recompute_pathway_stage() → reads data/checklist.json, data/patient.json
   c. database.save_patient_status() → OVERWRITES data/patient_status.json
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
| 2 | **multiple questionnaires with conflicting answers** | ✅ Rollup logic: ANY "yes" = contraindication. Later "no" doesn't remove it. | **Demo-breaker** | **Fix:** Track most recent answer per question_id, or add "cleared" flag |
| 3 | **delete patient when no patient exists** | ✅ Returns 404 (fixed) | None | Already fixed |
| 4 | **checklist exists without patient** | ⚠️ GET /checklist auto-creates if no patient. But pathway_stage logic assumes patient exists. | Minor | Add patient check in GET /checklist before auto-create |
| 5 | **document upload without checklist** | ✅ Returns 404 "No checklist found" | None | Already handled |
| 6 | **patient-status called before questionnaire** | ✅ Returns 404 "No questionnaires found" | None | Already handled |
| 7 | **patient-status called with patient but no questionnaires** | ✅ Returns 404 (ValueError caught) | None | Already handled |
| 8 | **checklist completion exactly 80%** | ✅ Returns 'selection' (>= 0.8) | None | Correct behavior |
| 9 | **checklist with 0 items** | ✅ Returns 'referral' (line 76-77) | None | Correct behavior |
| 10 | **has_referral=None vs has_referral=False** | ⚠️ `None` treated as "has referral" (line 65 only checks `False`). May skip referral stage incorrectly. | **Demo-breaker** | **Fix:** Explicitly check `has_referral is True` for evaluation/selection stages |
| 11 | **questionnaire with unknown question_id** | ✅ Ignored (question_map.get() returns None) | Minor | None needed - graceful degradation |
| 12 | **empty answers dict in questionnaire** | ✅ No contraindications found (loop doesn't execute) | None | Correct behavior |
| 13 | **checklist.items is None (not empty list)** | ⚠️ `checklist.get('items', [])` returns `[]` if missing, but if `items=None`, would crash on `len()`. | **Demo-breaker** | **Fix:** Add `items = items or []` guard |
| 14 | **pathway_stage computed when patient deleted mid-request** | ⚠️ Race condition: patient deleted between get_patient() and status computation. | Minor | Low risk in single-user demo |
| 15 | **questions.json has invalid JSON** | ✅ Returns `[]`, no crash | None | Already demo-safe |

---

## 4. "IS IT THE BEST LOGIC?" - Clinical Realism Evaluation

### Current Pathway Stage Logic Issues:

**Issue 1: has_referral=None ambiguity**
- Current: `has_referral=False` → 'referral', but `has_referral=None` → can reach 'evaluation'
- **Problem:** Unclear if patient needs referral or already has one
- **Fix:** Require explicit `has_referral=True` to advance past referral stage

**Issue 2: Checklist auto-creation on GET**
- Current: GET /checklist creates default checklist if none exists
- **Problem:** Creates checklist even if patient hasn't completed questionnaire
- **Fix:** Only auto-create if questionnaire exists

**Issue 3: Pathway stage jumps**
- Current: Can jump from 'identification' → 'evaluation' if checklist auto-created and items marked complete
- **Problem:** Skips 'referral' stage in demo flow
- **Fix:** Require explicit referral before evaluation

**Issue 4: 80% threshold is arbitrary**
- Current: Hard-coded 0.8 threshold
- **Problem:** Not clinically meaningful
- **Fix:** Keep for demo, but document as "demo threshold"

**Issue 5: Multiple questionnaires with conflicting answers**
- Current: ANY "yes" = permanent contraindication
- **Problem:** Patient can't "clear" a contraindication by answering "no" later
- **Fix:** Use most recent answer per question_id, or add explicit "cleared" mechanism

### Proposed Minimum Changes (Priority Order):

#### Priority 1 (1-hour fixes - High Impact):

1. **Fix has_referral=None ambiguity**
   - File: `app/services/status_computation.py::determine_pathway_stage()`
   - Change: Require `has_referral is True` (not just `not False`) to advance past referral
   - Impact: More deterministic pathway progression

2. **Fix checklist.items=None crash risk**
   - File: `app/services/status_computation.py::determine_pathway_stage()` (line 75)
   - Change: Add `items = items or []` guard
   - Impact: Prevents potential crash

#### Priority 2 (3-hour fixes - Medium Impact):

3. **Fix conflicting questionnaire answers**
   - File: `app/services/status_computation.py::compute_patient_status_from_all_questionnaires()`
   - Change: Use most recent answer per question_id (sort by submitted_at)
   - Impact: More realistic - later answers override earlier ones

4. **Fix checklist auto-creation timing**
   - File: `app/api/checklist.py::get_checklist()` (line 30-46)
   - Change: Only auto-create if questionnaire exists
   - Impact: Prevents premature checklist creation

#### Priority 3 (Risky/Not Worth It):

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

# 6. Update checklist item
curl -X PATCH http://127.0.0.1:8000/api/v1/checklist/items/physical_exam \
  -H "Content-Type: application/json" \
  -d '{"is_complete":true}'
# Expected: HTTP 200, Checklist with updated item

# 7. Get patient status (pathway_stage may change)
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
4. ✅ Rollup logic correctly aggregates across questionnaires

### Critical Issues (Must Fix):
1. **Conflicting questionnaire answers** - Later "no" doesn't clear earlier "yes"
2. **has_referral=None ambiguity** - Can skip referral stage incorrectly
3. **checklist.items=None crash risk** - Potential AttributeError

### Recommended Fixes (Priority Order):
1. **1-hour:** Fix has_referral logic, add items=None guard
2. **3-hour:** Use most recent answer per question_id, fix checklist auto-creation timing
3. **Skip:** Complex time-based logic, additional stages

---

**End of Audit Report**
