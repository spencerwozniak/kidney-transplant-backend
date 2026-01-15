"""
Export endpoints

Exports patient data in FHIR R4 format and generates AI-powered clinical summaries.
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Dict, Any, List, Optional
from pathlib import Path
import base64
import json
import asyncio
from datetime import datetime

from app.database import storage as database
from app.api.utils import get_device_id
from app.services.ai.service import build_patient_context, read_document_text
from app.services.ai.config import get_openai_client, get_default_model, is_ai_enabled

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
    
    Only includes .txt files (extracted text) rather than the original images/PDFs.
    Each document has a corresponding .txt file with the extracted text content.
    
    Args:
        checklist_data: Checklist dictionary containing document references
        patient_id: Patient ID
        
    Returns:
        List of FHIR DocumentReference resources with text content from .txt files
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
            # Construct full file path
            # Document paths are stored as: documents/{patient_id}/{item_id}/{filename}
            full_path = Path("data") / doc_path
            
            # Check if original file exists
            if not full_path.exists():
                continue
            
            # Look for corresponding .txt file
            txt_path = full_path.with_suffix(full_path.suffix + '.txt')
            
            # Only include documents that have a .txt file
            if not txt_path.exists():
                continue
            
            doc_counter += 1
            
            # Read text content from .txt file
            try:
                with open(txt_path, 'r', encoding='utf-8') as f:
                    text_content = f.read()
            except Exception:
                # If we can't read the text file, skip this document
                continue
            
            # Encode text content to base64
            try:
                text_bytes = text_content.encode('utf-8')
                base64_content = base64.b64encode(text_bytes).decode('utf-8')
            except Exception:
                continue
            
            # Extract original filename (without .txt extension)
            original_filename = full_path.name
            
            # Create DocumentReference with text content
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
                            "contentType": "text/plain",
                            "data": base64_content,
                            "title": original_filename,
                            "creation": datetime.fromtimestamp(txt_path.stat().st_mtime).isoformat() if txt_path.exists() else datetime.now().isoformat()
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
            
            # Add note that this is extracted text from the original document
            doc_ref["note"] = [
                {
                    "text": f"Extracted text content from {original_filename}"
                }
            ]
            
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


def format_context_for_clinical_summary(context: Dict[str, Any]) -> str:
    """
    Formats the patient context into a structured prompt for clinical summary generation
    
    Args:
        context: Patient context dictionary from build_patient_context
        
    Returns:
        Formatted string with all patient data for summary generation
    """
    sections = []
    
    # Patient Demographics
    patient = context.get("patient_summary", {})
    if patient:
        patient_lines = []
        if patient.get("has_ckd_esrd"):
            patient_lines.append("Diagnosis: CKD/ESRD confirmed")
        if patient.get("last_gfr") is not None:
            patient_lines.append(f"Last GFR: {patient.get('last_gfr')} mL/min/1.73m²")
        if patient.get("has_referral"):
            patient_lines.append("Has existing referral")
        if patient_lines:
            sections.append("PATIENT INFORMATION:\n" + "\n".join(patient_lines))
    
    # Pathway Stage
    pathway_stage = context.get("pathway_stage")
    if pathway_stage:
        stage_descriptions = {
            "identification": "Identification & Awareness - Early stage, learning about transplant options",
            "referral": "Referral Stage - Need to obtain referral to transplant center",
            "evaluation": "Evaluation Stage - Undergoing pre-transplant evaluation workup",
            "selection": "Selection & Waitlisting - Evaluation mostly complete, ready for waitlist consideration",
            "transplantation": "Transplantation - On waitlist or scheduled for transplant",
            "post-transplant": "Post-Transplant - Post-transplant care and monitoring"
        }
        stage_desc = stage_descriptions.get(pathway_stage, pathway_stage)
        sections.append(f"PATHWAY STAGE: {pathway_stage.upper()} - {stage_desc}")
    
    # Medical Status
    status = context.get("status_summary", {})
    if status:
        status_lines = []
        if status.get("has_absolute_contraindications"):
            status_lines.append("ABSOLUTE CONTRAINDICATIONS (may prevent transplant):")
            for contra in status.get("absolute_contraindications", []):
                status_lines.append(f"  • {contra.get('question')}")
        else:
            status_lines.append("No absolute contraindications identified")
        
        if status.get("has_relative_contraindications"):
            status_lines.append("\nRELATIVE CONTRAINDICATIONS (may need to be addressed):")
            for contra in status.get("relative_contraindications", []):
                status_lines.append(f"  • {contra.get('question')}")
        else:
            status_lines.append("No relative contraindications identified")
        
        if status_lines:
            sections.append("MEDICAL STATUS:\n" + "\n".join(status_lines))
    
    # Checklist Progress
    checklist = context.get("checklist_progress", {})
    if checklist and checklist.get("total_items", 0) > 0:
        checklist_lines = []
        checklist_lines.append(f"Progress: {checklist.get('completed_count')}/{checklist.get('total_items')} items complete ({checklist.get('completion_percentage')}%)")
        
        completed = checklist.get("completed_items", [])
        if completed:
            checklist_lines.append("\nCompleted Items:")
            for item in completed[:10]:  # Top 10 completed
                checklist_lines.append(f"  • {item.get('title')}")
                if item.get('notes'):
                    checklist_lines.append(f"    Notes: {item.get('notes')}")
        
        incomplete = checklist.get("incomplete_items", [])
        if incomplete:
            checklist_lines.append("\nRemaining Items:")
            for item in incomplete[:10]:  # Top 10 remaining
                checklist_lines.append(f"  • {item.get('title')}")
                if item.get('description'):
                    checklist_lines.append(f"    Description: {item.get('description')}")
        
        sections.append("CHECKLIST PROGRESS:\n" + "\n".join(checklist_lines))
    
    # Checklist Documents (extracted text)
    checklist_docs = context.get("checklist_documents", {})
    if checklist_docs:
        doc_sections = []
        for item_id, doc_data in checklist_docs.items():
            item_title = doc_data.get("title", "")
            documents = doc_data.get("documents", [])
            
            if documents:
                doc_sections.append(f"\n{item_title.upper()}:")
                # Include all document texts for this item
                for idx, doc_text in enumerate(documents, 1):
                    doc_sections.append(f"\nDocument {idx}:")
                    doc_sections.append(doc_text[:2000])  # Limit each document to 2000 chars
                    if len(doc_text) > 2000:
                        doc_sections.append("... (truncated)")
        
        if doc_sections:
            sections.append("UPLOADED DOCUMENTS:\n" + "\n".join(doc_sections))
    
    # Referral Information
    referral = context.get("referral_information", {})
    if referral:
        referral_lines = []
        if referral.get("has_referral"):
            referral_lines.append("Has referral to transplant center")
        else:
            referral_lines.append("Does NOT have referral yet")
        
        referral_status = referral.get("referral_status", "not_started")
        if referral_status != "not_started":
            referral_lines.append(f"Referral process status: {referral_status}")
        
        if referral.get("has_nephrologist"):
            referral_lines.append("Has a nephrologist who can provide referral")
        if referral.get("has_dialysis_center"):
            referral_lines.append("Has a dialysis center that can assist with referral")
        
        location = referral.get("location", {})
        if location:
            location_parts = []
            if location.get("city"):
                location_parts.append(location.get("city"))
            if location.get("state"):
                location_parts.append(location.get("state"))
            if location.get("zip"):
                location_parts.append(location.get("zip"))
            if location_parts:
                referral_lines.append(f"Location: {', '.join(location_parts)}")
        
        sections.append("REFERRAL INFORMATION:\n" + "\n".join(referral_lines))
    
    # Financial Profile
    financial = context.get("financial_profile", {})
    if financial and financial.get("has_profile"):
        financial_lines = []
        if financial.get("has_answers"):
            financial_lines.append(f"Financial assessment: {financial.get('completed_count')}/{financial.get('total_questions')} questions completed ({financial.get('completion_percentage')}%)")
            if financial.get("submitted_at"):
                financial_lines.append(f"Submitted: {financial.get('submitted_at')}")
        else:
            financial_lines.append("Financial assessment: Not yet started")
        
        sections.append("FINANCIAL PROFILE:\n" + "\n".join(financial_lines))
    
    return "\n\n".join(sections)


async def generate_clinical_summary_stream(patient_id: str, device_id: str, model: str = "gpt-5.1"):
    """
    Generate a clinical summary document using OpenAI with streaming
    
    Args:
        patient_id: Patient ID
        device_id: Device ID to get patient data
        model: OpenAI model to use (default: gpt-5.1)
        
    Yields:
        Text chunks as they are generated
    """
    if not is_ai_enabled():
        raise HTTPException(
            status_code=503,
            detail="AI features are not enabled. OPENAI_API_KEY environment variable not set."
        )
    
    # Build patient context (reuse from AI service)
    context = build_patient_context(patient_id, device_id)
    
    # Format context for summary generation
    context_str = format_context_for_clinical_summary(context)
    
    # Build system prompt for clinical summary
    system_prompt = """You are a medical documentation assistant helping to create a comprehensive clinical summary for a kidney transplant evaluation patient.

Your task is to generate a clear, professional clinical summary document that can be shared with healthcare providers and transplant centers.

Guidelines:
- Write in a professional, clinical tone suitable for medical documentation
- Organize information clearly with appropriate sections
- Include all relevant clinical information from the provided context
- Be concise but comprehensive
- Use standard medical terminology
- Do NOT provide medical advice, diagnoses, or treatment recommendations
- Focus on factual information from the patient's data
- Format the summary as a clean, readable document with clear sections
- Include relevant details from uploaded documents when available"""

    # Build user prompt
    user_prompt = f"""Generate a comprehensive clinical summary document for this patient based on the following information:

{context_str}

Please create a well-structured clinical summary document that includes:
1. Patient Demographics and Clinical Status
2. Current Pathway Stage and Progress
3. Medical Status and Contraindications
4. Pre-transplant Checklist Progress
5. Relevant Information from Uploaded Documents
6. Referral Status
7. Financial Assessment Status (if applicable)

Format the summary as a professional medical document that can be easily shared with healthcare providers."""

    try:
        client = get_openai_client()
        
        # Use streaming API
        stream = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_output_tokens=2000,
            stream=True
        )
        
        # Stream chunks with proper async yielding
        for event in stream:
            if event.type == "response.output_text.delta":
                yield event.delta
                await asyncio.sleep(0)  # Yield control to event loop for true streaming
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate clinical summary: {str(e)}"
        )


def generate_clinical_summary(patient_id: str, device_id: str, model: str = "gpt-5.1") -> str:
    """
    Generate a clinical summary document using OpenAI
    
    Args:
        patient_id: Patient ID
        device_id: Device ID to get patient data
        model: OpenAI model to use (default: gpt-5.1)
        
    Returns:
        Generated clinical summary text
    """
    if not is_ai_enabled():
        raise HTTPException(
            status_code=503,
            detail="AI features are not enabled. OPENAI_API_KEY environment variable not set."
        )
    
    # Build patient context (reuse from AI service)
    context = build_patient_context(patient_id, device_id)
    
    # Format context for summary generation
    context_str = format_context_for_clinical_summary(context)
    
    # Build system prompt for clinical summary
    system_prompt = """You are a medical documentation assistant helping to create a comprehensive clinical summary for a kidney transplant evaluation patient.

Your task is to generate a clear, professional clinical summary document that can be shared with healthcare providers and transplant centers.

Guidelines:
- Write in a professional, clinical tone suitable for medical documentation
- Organize information clearly with appropriate sections
- Include all relevant clinical information from the provided context
- Be concise but comprehensive
- Use standard medical terminology
- Do NOT provide medical advice, diagnoses, or treatment recommendations
- Focus on factual information from the patient's data
- Format the summary as a clean, readable document with clear sections
- Include relevant details from uploaded documents when available"""

    # Build user prompt
    user_prompt = f"""Generate a comprehensive clinical summary document for this patient based on the following information:

{context_str}

Please create a well-structured clinical summary document that includes:
1. Patient Demographics and Clinical Status
2. Current Pathway Stage and Progress
3. Medical Status and Contraindications
4. Pre-transplant Checklist Progress
5. Relevant Information from Uploaded Documents
6. Referral Status
7. Financial Assessment Status (if applicable)

Format the summary as a professional medical document that can be easily shared with healthcare providers."""

    try:
        client = get_openai_client()
        
        # Use standard OpenAI Chat Completions API
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,  # Lower temperature for more consistent, factual output
            max_tokens=2000  # Allow for comprehensive summary
        )
        
        summary = response.choices[0].message.content.strip()
        return summary
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate clinical summary: {str(e)}"
        )


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


@router.get("/patients/clinical-summary/stream")
async def export_clinical_summary_stream(request: Request, model: Optional[str] = None):
    """
    Generate and stream a comprehensive clinical summary document using AI
    
    This endpoint streams a professional clinical summary document that encompasses
    all patient data including demographics, medical status, checklist progress,
    uploaded documents (extracted text), referral status, and financial profile.
    
    The summary is generated using OpenAI and streamed as text chunks, allowing
    the user to see progress in real-time rather than waiting for the full response.
    
    Args:
        request: FastAPI request object (used to get device_id)
        model: Optional OpenAI model name (defaults to gpt-5.1)
        
    Returns:
        StreamingResponse with text chunks in Server-Sent Events format
    """
    device_id = get_device_id(request)
    
    # Verify patient exists
    patient_data = database.get_patient(device_id)
    if not patient_data:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    patient_id = patient_data.get('id')
    
    # Use provided model or default
    model_name = model or get_default_model()
    
    async def generate():
        try:
            chunk_count = 0
            
            # Stream clinical summary chunks
            async for chunk in generate_clinical_summary_stream(patient_id, device_id, model_name):
                chunk_count += 1
                # Send each text chunk as JSON
                chunk_json = f"data: {json.dumps({'chunk': chunk})}\n\n"
                yield chunk_json.encode('utf-8')
            
            # Send completion signal
            yield f"data: {json.dumps({'done': True})}\n\n".encode('utf-8')
        
        except HTTPException:
            raise
        except Exception as e:
            error_data = json.dumps({'error': str(e)})
            yield f"data: {error_data}\n\n".encode('utf-8')
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/patients/clinical-summary")
async def export_clinical_summary(request: Request, model: Optional[str] = None):
    """
    Generate and export a comprehensive clinical summary document using AI
    
    This endpoint generates a professional clinical summary document that encompasses
    all patient data including demographics, medical status, checklist progress,
    uploaded documents (extracted text), referral status, and financial profile.
    
    The summary is generated using OpenAI gpt-5.1 and is formatted as a clean,
    shareable document suitable for healthcare providers and transplant centers.
    
    Args:
        request: FastAPI request object (used to get device_id)
        model: Optional OpenAI model name (defaults to gpt-5.1)
        
    Returns:
        JSON response with the generated clinical summary
    """
    device_id = get_device_id(request)
    
    # Verify patient exists
    patient_data = database.get_patient(device_id)
    if not patient_data:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    patient_id = patient_data.get('id')
    
    # Use provided model or default
    model_name = model or get_default_model()
    
    # Generate clinical summary
    try:
        summary = generate_clinical_summary(patient_id, device_id, model_name)
        
        return JSONResponse(
            content={
                "summary": summary,
                "generated_at": datetime.now().isoformat(),
                "patient_id": patient_id,
                "model": model_name
            },
            media_type="application/json"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate clinical summary: {str(e)}"
        )

