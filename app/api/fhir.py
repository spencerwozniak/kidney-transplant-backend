"""
FHIR export endpoints

Exports patient data in FHIR R4 format, including all stored data and uploaded documents.
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
from pathlib import Path
import base64
from datetime import datetime

from app.database import storage as database
from app.api.utils import get_device_id

router = APIRouter()


def encode_document_to_base64(file_path: Path) -> Optional[str]:
    """
    Read a document file and encode it as base64
    
    Args:
        file_path: Path to the document file
        
    Returns:
        Base64 encoded string or None if file cannot be read
    """
    try:
        if not file_path.exists() or not file_path.is_file():
            return None
        with open(file_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except Exception:
        return None


def get_document_media_type(file_path: Path) -> str:
    """
    Determine FHIR media type from file extension
    
    Args:
        file_path: Path to the document file
        
    Returns:
        FHIR media type string
    """
    extension = file_path.suffix.lower()
    media_types = {
        '.pdf': 'application/pdf',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
        '.webp': 'image/webp',
    }
    return media_types.get(extension, 'application/octet-stream')


def create_fhir_patient(patient_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert patient data to FHIR Patient resource
    
    Args:
        patient_data: Patient dictionary from database
        
    Returns:
        FHIR Patient resource
    """
    patient_id = patient_data.get('id', '')
    
    # Parse date of birth
    dob = patient_data.get('date_of_birth', '')
    
    # Map sex
    sex_code = None
    sex = patient_data.get('sex', '').lower() if patient_data.get('sex') else None
    if sex == 'male':
        sex_code = 'male'
    elif sex == 'female':
        sex_code = 'female'
    elif sex == 'other':
        sex_code = 'other'
    
    # Build name
    name_parts = patient_data.get('name', '').split(' ', 1)
    given = [name_parts[0]] if len(name_parts) > 0 else []
    family = name_parts[1] if len(name_parts) > 1 else None
    
    patient = {
        "resourceType": "Patient",
        "id": patient_id,
        "identifier": [
            {
                "system": "urn:ietf:rfc:3986",
                "value": patient_id
            }
        ],
        "name": [
            {
                "use": "official",
                "family": family or "",
                "given": given
            }
        ],
        "telecom": [],
        "gender": sex_code,
        "birthDate": dob if dob else None,
    }
    
    # Add contact information
    if patient_data.get('email'):
        patient["telecom"].append({
            "system": "email",
            "value": patient_data.get('email'),
            "use": "home"
        })
    
    if patient_data.get('phone'):
        patient["telecom"].append({
            "system": "phone",
            "value": patient_data.get('phone'),
            "use": "home"
        })
    
    # Remove None values
    if not patient["telecom"]:
        del patient["telecom"]
    if not patient["gender"]:
        del patient["gender"]
    if not patient["birthDate"]:
        del patient["birthDate"]
    
    return patient


def create_fhir_observations(patient_data: Dict[str, Any], patient_id: str) -> List[Dict[str, Any]]:
    """
    Create FHIR Observation resources from patient data
    
    Args:
        patient_data: Patient dictionary from database
        patient_id: Patient ID
        
    Returns:
        List of FHIR Observation resources
    """
    observations = []
    
    # Height observation
    if patient_data.get('height') is not None:
        observations.append({
            "resourceType": "Observation",
            "id": f"{patient_id}-height",
            "status": "final",
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "8302-2",
                        "display": "Body height"
                    }
                ]
            },
            "subject": {
                "reference": f"Patient/{patient_id}"
            },
            "valueQuantity": {
                "value": patient_data.get('height'),
                "unit": "cm",
                "system": "http://unitsofmeasure.org",
                "code": "cm"
            }
        })
    
    # Weight observation
    if patient_data.get('weight') is not None:
        observations.append({
            "resourceType": "Observation",
            "id": f"{patient_id}-weight",
            "status": "final",
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "29463-7",
                        "display": "Body weight"
                    }
                ]
            },
            "subject": {
                "reference": f"Patient/{patient_id}"
            },
            "valueQuantity": {
                "value": patient_data.get('weight'),
                "unit": "kg",
                "system": "http://unitsofmeasure.org",
                "code": "kg"
            }
        })
    
    # GFR observation
    if patient_data.get('last_gfr') is not None:
        observations.append({
            "resourceType": "Observation",
            "id": f"{patient_id}-gfr",
            "status": "final",
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "33914-3",
                        "display": "Glomerular filtration rate/1.73 sq M.predicted"
                    }
                ]
            },
            "subject": {
                "reference": f"Patient/{patient_id}"
            },
            "valueQuantity": {
                "value": patient_data.get('last_gfr'),
                "unit": "mL/min/1.73m2",
                "system": "http://unitsofmeasure.org",
                "code": "mL/min/{1.73_m2}"
            }
        })
    
    # CKD/ESRD condition indicator
    if patient_data.get('has_ckd_esrd') is not None:
        observations.append({
            "resourceType": "Observation",
            "id": f"{patient_id}-ckd-esrd",
            "status": "final",
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "71802-3",
                        "display": "Chronic kidney disease stage"
                    }
                ]
            },
            "subject": {
                "reference": f"Patient/{patient_id}"
            },
            "valueBoolean": patient_data.get('has_ckd_esrd')
        })
    
    return observations


def create_fhir_questionnaire_responses(
    questionnaires: List[Dict[str, Any]], 
    patient_id: str
) -> List[Dict[str, Any]]:
    """
    Create FHIR QuestionnaireResponse resources from questionnaire submissions
    
    Args:
        questionnaires: List of questionnaire dictionaries
        patient_id: Patient ID
        
    Returns:
        List of FHIR QuestionnaireResponse resources
    """
    responses = []
    
    for idx, q in enumerate(questionnaires):
        q_id = q.get('id', f"{patient_id}-questionnaire-{idx}")
        submitted_at = q.get('submitted_at', datetime.now().isoformat())
        answers = q.get('answers', {})
        
        # Build answer items
        items = []
        for question_id, answer_value in answers.items():
            items.append({
                "linkId": question_id,
                "answer": [
                    {
                        "valueString": str(answer_value)
                    }
                ]
            })
        
        response = {
            "resourceType": "QuestionnaireResponse",
            "id": q_id,
            "status": "completed",
            "subject": {
                "reference": f"Patient/{patient_id}"
            },
            "authored": submitted_at,
            "item": items
        }
        
        responses.append(response)
    
    return responses


def create_fhir_conditions(
    status_data: Optional[Dict[str, Any]], 
    patient_id: str
) -> List[Dict[str, Any]]:
    """
    Create FHIR Condition resources from patient status (contraindications)
    
    Args:
        status_data: Patient status dictionary
        patient_id: Patient ID
        
    Returns:
        List of FHIR Condition resources
    """
    conditions = []
    
    if not status_data:
        return conditions
    
    # Absolute contraindications
    absolute_contraindications = status_data.get('absolute_contraindications', [])
    for idx, contra in enumerate(absolute_contraindications):
        conditions.append({
            "resourceType": "Condition",
            "id": f"{patient_id}-absolute-contra-{idx}",
            "clinicalStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": "active",
                        "display": "Active"
                    }
                ]
            },
            "severity": {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": "255604002",
                        "display": "Mild"
                    }
                ]
            },
            "code": {
                "text": contra.get('question', '')
            },
            "subject": {
                "reference": f"Patient/{patient_id}"
            },
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://snomed.info/sct",
                            "code": "64572001",
                            "display": "Disease"
                        }
                    ],
                    "text": "Absolute Contraindication"
                }
            ]
        })
    
    # Relative contraindications
    relative_contraindications = status_data.get('relative_contraindications', [])
    for idx, contra in enumerate(relative_contraindications):
        conditions.append({
            "resourceType": "Condition",
            "id": f"{patient_id}-relative-contra-{idx}",
            "clinicalStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": "active",
                        "display": "Active"
                    }
                ]
            },
            "severity": {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": "6736007",
                        "display": "Moderate"
                    }
                ]
            },
            "code": {
                "text": contra.get('question', '')
            },
            "subject": {
                "reference": f"Patient/{patient_id}"
            },
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://snomed.info/sct",
                            "code": "64572001",
                            "display": "Disease"
                        }
                    ],
                    "text": "Relative Contraindication"
                }
            ]
        })
    
    return conditions


def create_fhir_document_references(
    checklist_data: Optional[Dict[str, Any]], 
    patient_id: str
) -> List[Dict[str, Any]]:
    """
    Create FHIR DocumentReference resources from uploaded documents
    
    Args:
        checklist_data: Checklist dictionary containing document references
        patient_id: Patient ID
        
    Returns:
        List of FHIR DocumentReference resources with base64 encoded content
    """
    document_references = []
    
    if not checklist_data:
        return document_references
    
    items = checklist_data.get('items', [])
    doc_counter = 0
    
    for item in items:
        item_id = item.get('id', '')
        documents = item.get('documents', [])
        
        for doc_path in documents:
            doc_counter += 1
            
            # Construct full file path
            # Document paths are stored as: documents/{patient_id}/{item_id}/{filename}
            full_path = Path("data") / doc_path
            
            # Check if file exists
            if not full_path.exists():
                continue
            
            # Encode document to base64
            base64_content = encode_document_to_base64(full_path)
            if not base64_content:
                continue
            
            # Get media type
            media_type = get_document_media_type(full_path)
            
            # Extract filename
            filename = full_path.name
            
            # Create DocumentReference
            doc_ref = {
                "resourceType": "DocumentReference",
                "id": f"{patient_id}-doc-{doc_counter}",
                "status": "current",
                "type": {
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": "51852-2",
                            "display": "Clinical note"
                        }
                    ],
                    "text": item.get('title', 'Checklist Item Document')
                },
                "subject": {
                    "reference": f"Patient/{patient_id}"
                },
                "date": datetime.now().isoformat(),
                "content": [
                    {
                        "attachment": {
                            "contentType": media_type,
                            "data": base64_content,
                            "title": filename,
                            "creation": datetime.fromtimestamp(full_path.stat().st_mtime).isoformat() if full_path.exists() else datetime.now().isoformat()
                        }
                    }
                ],
                "context": {
                    "related": [
                        {
                            "reference": f"Patient/{patient_id}",
                            "display": "Patient Record"
                        }
                    ]
                }
            }
            
            # Add description from checklist item
            if item.get('description'):
                doc_ref["description"] = item.get('description')
            
            document_references.append(doc_ref)
    
    return document_references


def create_fhir_bundle(
    patient: Dict[str, Any],
    observations: List[Dict[str, Any]],
    questionnaire_responses: List[Dict[str, Any]],
    conditions: List[Dict[str, Any]],
    document_references: List[Dict[str, Any]],
    checklist_data: Optional[Dict[str, Any]] = None,
    status_data: Optional[Dict[str, Any]] = None,
    financial_profile: Optional[Dict[str, Any]] = None,
    referral_state: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a FHIR Bundle containing all patient resources
    
    Args:
        patient: FHIR Patient resource
        observations: List of FHIR Observation resources
        questionnaire_responses: List of FHIR QuestionnaireResponse resources
        conditions: List of FHIR Condition resources
        document_references: List of FHIR DocumentReference resources
        checklist_data: Optional checklist data for additional context
        status_data: Optional status data for additional context
        financial_profile: Optional financial profile data
        referral_state: Optional referral state data
        
    Returns:
        FHIR Bundle resource
    """
    # Collect all resources
    entries = []
    
    # Add patient
    entries.append({
        "fullUrl": f"Patient/{patient['id']}",
        "resource": patient
    })
    
    # Add observations
    for obs in observations:
        entries.append({
            "fullUrl": f"Observation/{obs['id']}",
            "resource": obs
        })
    
    # Add questionnaire responses
    for qr in questionnaire_responses:
        entries.append({
            "fullUrl": f"QuestionnaireResponse/{qr['id']}",
            "resource": qr
        })
    
    # Add conditions
    for condition in conditions:
        entries.append({
            "fullUrl": f"Condition/{condition['id']}",
            "resource": condition
        })
    
    # Add document references
    for doc_ref in document_references:
        entries.append({
            "fullUrl": f"DocumentReference/{doc_ref['id']}",
            "resource": doc_ref
        })
    
    # Create bundle
    bundle = {
        "resourceType": "Bundle",
        "id": f"patient-export-{patient['id']}",
        "type": "collection",
        "timestamp": datetime.now().isoformat(),
        "entry": entries
    }
    
    # Add metadata as extension (non-standard, but useful for context)
    extensions = []
    
    if checklist_data:
        extensions.append({
            "url": "http://example.org/fhir/StructureDefinition/checklist-metadata",
            "valueString": f"Checklist created: {checklist_data.get('created_at', 'N/A')}, Updated: {checklist_data.get('updated_at', 'N/A')}"
        })
    
    if status_data:
        pathway_stage = status_data.get('pathway_stage')
        if pathway_stage:
            extensions.append({
                "url": "http://example.org/fhir/StructureDefinition/pathway-stage",
                "valueString": pathway_stage
            })
    
    if financial_profile:
        extensions.append({
            "url": "http://example.org/fhir/StructureDefinition/financial-profile",
            "valueString": f"Financial profile submitted: {financial_profile.get('submitted_at', 'N/A')}"
        })
    
    if referral_state:
        has_referral = referral_state.get('has_referral', False)
        extensions.append({
            "url": "http://example.org/fhir/StructureDefinition/referral-status",
            "valueString": f"Has referral: {has_referral}, Status: {referral_state.get('referral_status', 'N/A')}"
        })
    
    if extensions:
        bundle["extension"] = extensions
    
    return bundle


@router.get("/patients/fhir")
async def export_patient_fhir(request: Request):
    """
    Export all patient data in FHIR R4 format for the current device's patient
    
    This endpoint aggregates all data stored for a patient and returns it as a FHIR Bundle
    containing:
    - Patient resource (demographics)
    - Observation resources (height, weight, GFR, CKD/ESRD status)
    - QuestionnaireResponse resources (all questionnaire submissions)
    - Condition resources (contraindications)
    - DocumentReference resources (all uploaded documents with base64 encoded content)
    
    The bundle includes all uploaded documents as base64-encoded attachments in DocumentReference
    resources, making it a complete export of the patient's data.
    
    Uses X-Device-ID header to identify the patient (consistent with other endpoints).
    
    Args:
        request: FastAPI request object (used to get device_id)
        
    Returns:
        FHIR Bundle containing all patient resources
    """
    device_id = get_device_id(request)
    
    # Verify patient exists
    patient_data = database.get_patient(device_id)
    if not patient_data:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    patient_id = patient_data.get('id')
    
    # Gather all patient data
    questionnaires = database.get_all_questionnaires_for_patient(patient_id, device_id)
    checklist_data = database.get_checklist(device_id)
    status_data = database.get_patient_status(device_id)
    financial_profile = database.get_financial_profile(device_id)
    referral_state = database.get_patient_referral_state(device_id)
    
    # Create FHIR resources
    fhir_patient = create_fhir_patient(patient_data)
    fhir_observations = create_fhir_observations(patient_data, patient_id)
    fhir_questionnaire_responses = create_fhir_questionnaire_responses(questionnaires, patient_id)
    fhir_conditions = create_fhir_conditions(status_data, patient_id)
    fhir_document_references = create_fhir_document_references(checklist_data, patient_id)
    
    # Create FHIR Bundle
    bundle = create_fhir_bundle(
        patient=fhir_patient,
        observations=fhir_observations,
        questionnaire_responses=fhir_questionnaire_responses,
        conditions=fhir_conditions,
        document_references=fhir_document_references,
        checklist_data=checklist_data,
        status_data=status_data,
        financial_profile=financial_profile,
        referral_state=referral_state
    )
    
    return JSONResponse(content=bundle, media_type="application/fhir+json")


@router.get("/patients/{patient_id}/fhir")
async def export_patient_fhir_by_id(patient_id: str, request: Request):
    """
    Export all patient data in FHIR R4 format by patient ID
    
    This endpoint aggregates all data stored for a patient and returns it as a FHIR Bundle.
    Same as GET /patients/fhir but allows specifying patient_id in the path.
    
    Args:
        patient_id: Patient ID to export
        request: FastAPI request object (used to get device_id)
        
    Returns:
        FHIR Bundle containing all patient resources
    """
    device_id = get_device_id(request)
    
    # Verify patient exists and matches device
    patient_data = database.get_patient(device_id)
    if not patient_data:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Verify patient_id matches
    if patient_data.get('id') != patient_id:
        raise HTTPException(status_code=403, detail="Patient ID does not match current patient")
    
    # Gather all patient data
    questionnaires = database.get_all_questionnaires_for_patient(patient_id, device_id)
    checklist_data = database.get_checklist(device_id)
    status_data = database.get_patient_status(device_id)
    financial_profile = database.get_financial_profile(device_id)
    referral_state = database.get_patient_referral_state(device_id)
    
    # Create FHIR resources
    fhir_patient = create_fhir_patient(patient_data)
    fhir_observations = create_fhir_observations(patient_data, patient_id)
    fhir_questionnaire_responses = create_fhir_questionnaire_responses(questionnaires, patient_id)
    fhir_conditions = create_fhir_conditions(status_data, patient_id)
    fhir_document_references = create_fhir_document_references(checklist_data, patient_id)
    
    # Create FHIR Bundle
    bundle = create_fhir_bundle(
        patient=fhir_patient,
        observations=fhir_observations,
        questionnaire_responses=fhir_questionnaire_responses,
        conditions=fhir_conditions,
        document_references=fhir_document_references,
        checklist_data=checklist_data,
        status_data=status_data,
        financial_profile=financial_profile,
        referral_state=referral_state
    )
    
    return JSONResponse(content=bundle, media_type="application/fhir+json")

