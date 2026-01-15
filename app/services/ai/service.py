"""
AI Assistant Service

Constructs prompts and interacts with LLM providers to provide
personalized responses about patient's transplant journey.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import asyncio
from pathlib import Path

from app.database import storage as database
from app.database.schemas import PatientStatus
from app.services.patient_details import extract_personal_details


def read_document_text(document_path: str) -> Optional[str]:
    """
    Read text content from a document's .txt file
    
    Args:
        document_path: Relative path like "documents/{patient_id}/{item_id}/{filename}"
    
    Returns:
        Text content if file exists, None otherwise
    """
    try:
        # Convert relative path to full path: data/documents/... -> data/documents/....txt
        # The .txt file is stored at the same location with .txt appended to filename
        full_path = Path("data") / document_path
        text_file_path = full_path.with_name(full_path.name + '.txt')
        
        if text_file_path.exists() and text_file_path.is_file():
            with open(text_file_path, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        # If reading fails, return None
        pass
    return None


def build_patient_context(patient_id: str, device_id: str) -> Dict[str, Any]:
    """
    Aggregates all patient data into a structured context for AI prompts
    
    Args:
        patient_id: Patient ID to build context for
        device_id: Device ID to get patient data
    
    Returns:
        Dictionary containing structured patient context
    """
    # Fetch all data sources with error handling
    try:
        patient = database.get_patient(device_id)
    except Exception:
        patient = None
    
    try:
        status_data = database.get_patient_status(device_id)
    except Exception:
        status_data = None
    
    try:
        checklist_data = database.get_checklist(device_id)
    except Exception:
        checklist_data = None
    
    try:
        questionnaires = database.get_all_questionnaires_for_patient(patient_id, device_id)
    except Exception:
        questionnaires = None
    
    try:
        financial_profile = database.get_financial_profile(device_id)
    except Exception:
        financial_profile = None
    
    try:
        referral_state = database.get_patient_referral_state(device_id)
    except Exception:
        referral_state = None
    
    # Build context object
    context = {
        "patient_summary": {},
        "pathway_stage": None,
        "status_summary": {},
        "checklist_progress": {},
        "checklist_documents": {},
        "recent_activity": {},
        "referral_information": {},
        "financial_profile": {}
    }
    
    # Patient Summary
    if patient and isinstance(patient, dict):
        personal_details, _ = extract_personal_details(patient)
        context["patient_summary"] = {
            "has_ckd_esrd": patient.get("has_ckd_esrd"),
            "last_gfr": patient.get("last_gfr"),
            "has_referral": patient.get("has_referral"),
        }
        context["patient_details"] = personal_details
    
    # Pathway Stage & Status Summary
    if status_data and isinstance(status_data, dict):
        try:
            status = PatientStatus(**status_data)
            context["pathway_stage"] = getattr(status, "pathway_stage", None)
            context["status_summary"] = {
                "has_absolute_contraindications": getattr(status, "has_absolute", False),
                "has_relative_contraindications": getattr(status, "has_relative", False),
                "absolute_contraindications": [
                    {
                        "question": getattr(c, "question", str(c) if c else "")
                    }
                    for c in (getattr(status, "absolute_contraindications", None) or [])
                    if c is not None
                ],
                "relative_contraindications": [
                    {
                        "question": getattr(c, "question", str(c) if c else "")
                    }
                    for c in (getattr(status, "relative_contraindications", None) or [])
                    if c is not None
                ],
                "status_updated_at": getattr(status, "updated_at", None).isoformat() if hasattr(status, "updated_at") and getattr(status, "updated_at", None) else None
            }
        except Exception:
            # If status data is malformed, use basic info
            context["pathway_stage"] = status_data.get("pathway_stage") if isinstance(status_data, dict) else None
            context["status_summary"] = {
                "has_absolute_contraindications": status_data.get("has_absolute", False) if isinstance(status_data, dict) else False,
                "has_relative_contraindications": status_data.get("has_relative", False) if isinstance(status_data, dict) else False,
                "absolute_contraindications": [],
                "relative_contraindications": [],
                "status_updated_at": None
            }
    
    # Checklist Progress
    if checklist_data and isinstance(checklist_data, dict):
        try:
            items = checklist_data.get("items", []) or []
            # Ensure items is a list and filter out non-dict items
            if not isinstance(items, list):
                items = []
            items = [item for item in items if isinstance(item, dict)]
            
            completed_items = [item for item in items if item.get("is_complete", False)]
            incomplete_items = [item for item in items if not item.get("is_complete", False)]
            
            total_items = len(items)
            completed_count = len(completed_items)
            completion_percentage = (completed_count / total_items * 100) if total_items > 0 else 0
            
            context["checklist_progress"] = {
                "total_items": total_items,
                "completed_count": completed_count,
                "incomplete_count": len(incomplete_items),
                "completion_percentage": round(completion_percentage, 1),
                "completed_items": [
                    {
                        "title": item.get("title", ""),
                        "completed_at": item.get("completed_at"),
                        "notes": item.get("notes")
                    }
                    for item in completed_items[:5]  # Last 5 completed
                ],
                "incomplete_items": [
                    {
                        "title": item.get("title", ""),
                        "description": item.get("description", ""),
                        "order": item.get("order", 0),
                        "notes": item.get("notes")
                    }
                    for item in sorted(incomplete_items, key=lambda x: x.get("order", 0) if isinstance(x, dict) else 0)[:5]  # Next 5 to complete
                ]
            }
            
            # Extract document contents for all checklist items
            checklist_documents = {}
            for item in items:
                if isinstance(item, dict):
                    item_id = item.get("id")
                    item_title = item.get("title", "")
                    documents = item.get("documents", [])
                    
                    if item_id and documents and isinstance(documents, list):
                        # Read text content from all documents for this item
                        document_texts = []
                        for doc_path in documents:
                            if isinstance(doc_path, str):
                                text_content = read_document_text(doc_path)
                                if text_content:
                                    document_texts.append(text_content)
                        
                        # Only add to context if there are documents with text
                        if document_texts:
                            checklist_documents[item_id] = {
                                "title": item_title,
                                "documents": document_texts
                            }
            
            if checklist_documents:
                context["checklist_documents"] = checklist_documents
            
            # Most recent activity
            if items:
                items_with_dates = [
                    item for item in items 
                    if isinstance(item, dict) and (item.get("completed_at") or item.get("updated_at"))
                ]
                if items_with_dates:
                    try:
                        # Sort by completed_at or updated_at
                        most_recent = max(
                            items_with_dates,
                            key=lambda x: x.get("completed_at") or x.get("updated_at") or ""
                        )
                        if isinstance(most_recent, dict):
                            context["recent_activity"] = {
                                "last_item": most_recent.get("title", ""),
                                "last_activity_date": most_recent.get("completed_at") or most_recent.get("updated_at")
                            }
                    except (ValueError, TypeError):
                        # If max fails (e.g., all dates are None or invalid), skip
                        pass
        except Exception:
            # If checklist processing fails, leave checklist_progress empty
            pass
    
    # Questionnaire History
    if questionnaires and isinstance(questionnaires, list) and len(questionnaires) > 0:
        try:
            # Filter to ensure all items are dicts
            valid_questionnaires = [q for q in questionnaires if isinstance(q, dict)]
            if valid_questionnaires:
                # Get most recent questionnaire
                latest_questionnaire = max(
                    valid_questionnaires,
                    key=lambda q: q.get("submitted_at", "") or ""
                )
                if isinstance(latest_questionnaire, dict):
                    # Ensure recent_activity exists
                    if "recent_activity" not in context:
                        context["recent_activity"] = {}
                    context["recent_activity"]["last_questionnaire_date"] = latest_questionnaire.get("submitted_at")
        except (ValueError, TypeError, AttributeError):
            # If max fails or data is malformed, skip
            pass
    
    # Referral Information
    if referral_state and isinstance(referral_state, dict):
        try:
            last_nephrologist = referral_state.get("last_nephrologist")
            dialysis_center = referral_state.get("dialysis_center")
            
            # Safely access nested dicts
            has_nephrologist = False
            if isinstance(last_nephrologist, dict):
                has_nephrologist = bool(last_nephrologist.get("name"))
            
            has_dialysis_center = False
            if isinstance(dialysis_center, dict):
                has_dialysis_center = bool(dialysis_center.get("name"))
            
            preferred_centers = referral_state.get("preferred_centers", [])
            if not isinstance(preferred_centers, list):
                preferred_centers = []
            
            location = referral_state.get("location", {})
            if not isinstance(location, dict):
                location = {}
            
            context["referral_information"] = {
                "has_referral": referral_state.get("has_referral", False),
                "referral_status": referral_state.get("referral_status", "not_started"),
                "has_nephrologist": has_nephrologist,
                "has_dialysis_center": has_dialysis_center,
                "preferred_centers_count": len(preferred_centers),
                "location": location
            }
        except Exception:
            # If referral processing fails, use defaults
            context["referral_information"] = {
                "has_referral": False,
                "referral_status": "not_started",
                "has_nephrologist": False,
                "has_dialysis_center": False,
                "preferred_centers_count": 0,
                "location": {}
            }
    
    # Financial Profile
    if financial_profile and isinstance(financial_profile, dict):
        try:
            answers = financial_profile.get("answers", {})
            if not isinstance(answers, dict):
                answers = {}
            
            # Count completed answers (non-null values)
            completed_answers = {k: v for k, v in answers.items() if v is not None and v != ""}
            total_questions = len(answers)
            completed_count = len(completed_answers)
            
            context["financial_profile"] = {
                "has_profile": True,
                "total_questions": total_questions,
                "completed_count": completed_count,
                "completion_percentage": round((completed_count / total_questions * 100) if total_questions > 0 else 0, 1),
                "submitted_at": financial_profile.get("submitted_at"),
                "updated_at": financial_profile.get("updated_at"),
                "has_answers": completed_count > 0
            }
        except Exception:
            # If financial profile processing fails, use defaults
            context["financial_profile"] = {
                "has_profile": False,
                "total_questions": 0,
                "completed_count": 0,
                "completion_percentage": 0,
                "submitted_at": None,
                "updated_at": None,
                "has_answers": False
            }
    else:
        context["financial_profile"] = {
            "has_profile": False,
            "total_questions": 0,
            "completed_count": 0,
            "completion_percentage": 0,
            "submitted_at": None,
            "updated_at": None,
            "has_answers": False
        }
    
    return context


def _get_latest_questionnaire_answers(questionnaires: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Latest answer wins across questionnaires (newest submission takes precedence).
    """
    if not questionnaires or not isinstance(questionnaires, list):
        return {}

    def get_sort_key(q: Dict[str, Any]) -> str:
        submitted_at = q.get("submitted_at")
        if submitted_at is None:
            return "0000-00-00T00:00:00"
        if isinstance(submitted_at, str):
            return submitted_at
        if hasattr(submitted_at, "isoformat"):
            return submitted_at.isoformat()
        return str(submitted_at)

    questionnaires_sorted = sorted(questionnaires, key=get_sort_key, reverse=True)
    latest_answers: Dict[str, Any] = {}
    for questionnaire in questionnaires_sorted:
        answers = questionnaire.get("answers", {})
        if isinstance(answers, dict):
            for question_id, answer in answers.items():
                if question_id not in latest_answers:
                    latest_answers[question_id] = answer
    return latest_answers


def build_prediction_features(patient_id: str, device_id: str) -> Dict[str, Any]:
    """
    Build the structured feature input for prediction/debugging.
    """
    patient = database.get_patient(device_id) or {}
    personal_details, sources = extract_personal_details(patient)

    questionnaires = database.get_all_questionnaires_for_patient(patient_id, device_id) or []
    latest_answers = _get_latest_questionnaire_answers(questionnaires)

    features = {
        "features_version": "v1",
        "generated_at": datetime.utcnow().isoformat(),
        "dob": personal_details.get("dob"),
        "sex_assigned_at_birth": personal_details.get("sex_assigned_at_birth"),
        "height_cm": personal_details.get("height_cm"),
        "weight_kg": personal_details.get("weight_kg"),
        "weight_lbs": personal_details.get("weight_lbs"),
        "age_years": personal_details.get("age_years"),
        "bmi": personal_details.get("bmi"),
        "questionnaire_answers": latest_answers,
    }

    source_fields = {
        "dob": sources.get("dob"),
        "sex_assigned_at_birth": sources.get("sex_assigned_at_birth"),
        "height_cm": sources.get("height_cm"),
        "weight_kg": sources.get("weight_kg"),
        "weight_lbs": sources.get("weight_lbs"),
        "age_years": sources.get("age_years"),
        "bmi": sources.get("bmi"),
        "questionnaire_answers": {"from": "questionnaires", "transform": "latest_answer_wins"},
    }

    return {
        "features": features,
        "source_fields": source_fields,
    }


def format_context_for_prompt(context: Dict[str, Any]) -> str:
    """
    Formats the patient context into a readable string for the AI prompt
    Uses HTML-like tags to structure sections for better parsing
    
    Args:
        context: Patient context dictionary
    
    Returns:
        Formatted string describing patient's current state
    """
    sections = []
    
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
        pathway_content = f"{pathway_stage.upper()} - {stage_desc}"
        sections.append(f"<pathway_stage>\n{pathway_content}\n</pathway_stage>")

    # Personal Details
    details = context.get("patient_details", {})
    if details:
        detail_lines = [
            f"DOB: {details.get('dob') or 'unknown'}",
            f"Sex assigned at birth: {details.get('sex_assigned_at_birth') or 'unknown'}",
            f"Height (cm): {details.get('height_cm') if details.get('height_cm') is not None else 'unknown'}",
            f"Weight (lbs): {details.get('weight_lbs') if details.get('weight_lbs') is not None else 'unknown'}",
        ]
        sections.append(f"<personal_details>\n" + "\n".join(detail_lines) + "\n</personal_details>")
    
    # Status Summary
    status = context.get("status_summary", {})
    if status:
        status_lines = []
        if status.get("has_absolute_contraindications"):
            status_lines.append("Has ABSOLUTE contraindications (these may prevent transplant):")
            for contra in status.get("absolute_contraindications", []):
                status_lines.append(f"  • {contra.get('question')}")
        else:
            status_lines.append("No absolute contraindications identified")
        
        if status.get("has_relative_contraindications"):
            status_lines.append("\nHas RELATIVE contraindications (these may need to be addressed):")
            for contra in status.get("relative_contraindications", []):
                status_lines.append(f"  • {contra.get('question')}")
        else:
            status_lines.append("No relative contraindications identified")
        
        if status_lines:
            sections.append(f"<medical_status>\n" + "\n".join(status_lines) + "\n</medical_status>")
    
    # Checklist Progress
    checklist = context.get("checklist_progress", {})
    if checklist and checklist.get("total_items", 0) > 0:
        checklist_lines = []
        checklist_lines.append(f"Progress: {checklist.get('completed_count')}/{checklist.get('total_items')} items complete ({checklist.get('completion_percentage')}%)")
        
        incomplete = checklist.get("incomplete_items", [])
        if incomplete:
            checklist_lines.append("\nNext Items to Complete:")
            for item in incomplete[:3]:  # Top 3 next items
                checklist_lines.append(f"  • {item.get('title')}")
                if item.get('description'):
                    checklist_lines.append(f"    ({item.get('description')})")
                if item.get('notes'):
                    checklist_lines.append(f"    Notes: {item.get('notes')}")
        
        # Include notes from completed items if available
        completed = checklist.get("completed_items", [])
        if completed:
            items_with_notes = [item for item in completed if item.get('notes')]
            if items_with_notes:
                checklist_lines.append("\nRecent Completed Items with Notes:")
                for item in items_with_notes[:3]:  # Top 3 completed items with notes
                    checklist_lines.append(f"  • {item.get('title')}")
                    checklist_lines.append(f"    Notes: {item.get('notes')}")
        
        sections.append(f"<checklist_progress>\n" + "\n".join(checklist_lines) + "\n</checklist_progress>")
    
    # Checklist Documents
    checklist_docs = context.get("checklist_documents", {})
    if checklist_docs:
        for item_id, doc_data in checklist_docs.items():
            item_title = doc_data.get("title", "")
            documents = doc_data.get("documents", [])
            
            if documents:
                doc_lines = [f"<checklist_item id=\"{item_id}\" title=\"{item_title}\">"]
                # Combine all document texts for this item
                combined_text = "\n\n---\n\n".join(documents)
                doc_lines.append(combined_text)
                doc_lines.append("</checklist_item>")
                sections.append("\n".join(doc_lines))
    
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
            referral_lines.append(f"Referral process: {referral_status}")
        
        if referral.get("has_nephrologist"):
            referral_lines.append("Has a nephrologist who can provide referral")
        if referral.get("has_dialysis_center"):
            referral_lines.append("Has a dialysis center that can assist with referral")
        
        sections.append(f"<referral_status>\n" + "\n".join(referral_lines) + "\n</referral_status>")
    
    # Recent Activity
    activity = context.get("recent_activity", {})
    if activity.get("last_item"):
        activity_lines = [f"Last completed item: {activity.get('last_item')}"]
        if activity.get("last_activity_date"):
            activity_lines.append(f"Date: {activity.get('last_activity_date')}")
        if activity.get("last_questionnaire_date"):
            activity_lines.append(f"Last questionnaire submitted: {activity.get('last_questionnaire_date')}")
        sections.append(f"<recent_activity>\n" + "\n".join(activity_lines) + "\n</recent_activity>")
    
    # Financial Profile
    financial = context.get("financial_profile", {})
    if financial and financial.get("has_profile"):
        financial_lines = []
        if financial.get("has_answers"):
            financial_lines.append(f"Financial assessment: {financial.get('completed_count')}/{financial.get('total_questions')} questions completed ({financial.get('completion_percentage')}%)")
            if financial.get("submitted_at"):
                financial_lines.append(f"Submitted: {financial.get('submitted_at')}")
            elif financial.get("updated_at"):
                financial_lines.append(f"Last updated: {financial.get('updated_at')}")
        else:
            financial_lines.append("Financial assessment: Not yet started")
        
        if financial_lines:
            sections.append(f"<financial_profile>\n" + "\n".join(financial_lines) + "\n</financial_profile>")
    
    return "\n\n".join(sections)


def build_system_prompt() -> str:
    """
    Returns the system prompt that defines the AI assistant's role and constraints
    """
    return """You are a helpful, empathetic assistant for patients navigating the kidney transplant journey. 

CRITICAL: Keep responses BRIEF and CONCISE. Aim for 4-6 sentences maximum. Only include the most essential information that directly answers the question.

FORMATTING: Use markdown to make responses visually appealing:
- Use **bold** for emphasis on key points
- Use bullet points (-) for lists when helpful
- Use line breaks for readability
- Keep formatting minimal but effective

Your role is to:
- Provide brief, direct answers to patient questions
- Focus only on the most important information relevant to their question
- Be specific and actionable, not verbose

IMPORTANT CONSTRAINTS:
- You are NOT providing medical advice, diagnoses, or treatment recommendations
- Always refer patients to their healthcare providers (nephrologist, transplant team) for medical questions
- Use the patient's actual data provided in the context to personalize your responses
- If you don't have information about something, say so briefly rather than guessing
- Avoid repetition, elaboration, or unnecessary context
- Answer the question directly and stop - do not add extra explanations unless critical"""


def build_user_prompt(user_query: str, context: Dict[str, Any]) -> str:
    """
    Builds the user prompt combining their query with patient context
    
    Args:
        user_query: The patient's question
        context: Patient context dictionary
    
    Returns:
        Formatted prompt string
    """
    context_str = format_context_for_prompt(context)
    
    prompt = f"""<patient_context>
{context_str}
</patient_context>

<patient_question>
{user_query}
</patient_question>

<instructions>
Provide a BRIEF, direct answer (2-4 sentences max). Only include information that directly answers the question. 
Be specific and actionable. Do not elaborate or add unnecessary context. Remember: you are not providing medical advice.

Use markdown formatting (bold, bullet points, line breaks) to make the response visually appealing and easy to read.
</instructions>"""
    
    return prompt


def call_llm(system_prompt: str, user_prompt: str, provider: str = "openai", model: str = "gpt-5.1") -> str:
    """
    Calls the LLM provider with the constructed prompts
    
    Args:
        system_prompt: System prompt defining AI role
        user_prompt: User prompt with query and context
        provider: LLM provider ("openai", "anthropic", etc.)
        model: Model name to use
    
    Returns:
        AI response string
    
    Raises:
        NotImplementedError: If provider is not implemented
        Exception: If API call fails
    """
    # This is a placeholder - actual implementation will depend on chosen provider
    # For now, we'll implement OpenAI as the default
    
    if provider == "openai":
        try:
            import openai
            from app.services.ai.config import get_openai_client
            
            client = get_openai_client()
            
            response = client.responses.create(
                model=model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_output_tokens=200
            )
            
            return response.output_text.strip()
        
        except ImportError:
            raise ImportError("openai package not installed. Install with: pip install openai")
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")
    
    elif provider == "anthropic":
        # Placeholder for Anthropic Claude
        raise NotImplementedError("Anthropic provider not yet implemented")
    
    else:
        raise NotImplementedError(f"Provider '{provider}' not implemented")


async def call_llm_stream(system_prompt: str, user_prompt: str, provider: str = "openai", model: str = "gpt-5.1"):
    """
    Calls the LLM provider with streaming enabled (async)
    
    Uses async generator with asyncio.sleep(0) to ensure proper event loop
    yielding for true streaming, especially important when running behind
    AWS load balancers or API Gateway which may buffer responses.
    
    Args:
        system_prompt: System prompt defining AI role
        user_prompt: User prompt with query and context
        provider: LLM provider ("openai", "anthropic", etc.)
        model: Model name to use
    
    Yields:
        Text chunks as they are generated
    
    Raises:
        NotImplementedError: If provider is not implemented
        Exception: If API call fails
    """
    if provider == "openai":
        try:
            from app.services.ai.config import get_openai_client
            client = get_openai_client()
            
            stream = client.responses.create(
                model=model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_output_tokens=200,
                stream=True
            )
            
            # Adapt sync iterator → async stream
            # await asyncio.sleep(0) yields control back to event loop
            # This ensures chunks are sent immediately rather than buffered
            # Critical for true streaming behind AWS load balancers/API Gateway
            for event in stream:
                if event.type == "response.output_text.delta":
                    yield event.delta
                    await asyncio.sleep(0)  # Yield control to event loop for true streaming

        
        except ImportError:
            raise ImportError("openai package not installed. Install with: pip install openai")
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")
    
    elif provider == "anthropic":
        # Placeholder for Anthropic Claude
        raise NotImplementedError("Anthropic provider not yet implemented")
    
    else:
        raise NotImplementedError(f"Provider '{provider}' not implemented")


def get_ai_response(patient_id: str, user_query: str, device_id: str, provider: str = "openai", model: str = "gpt-5.1") -> str:
    """
    Main function to get AI response for a patient query
    
    Args:
        patient_id: Patient ID
        user_query: Patient's question
        device_id: Device ID to get patient data
        provider: LLM provider to use
        model: Model name to use
    
    Returns:
        AI response string
    """
    # Build patient context
    context = build_patient_context(patient_id, device_id)
    
    # Build prompts
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(user_query, context)
    
    # Call LLM
    response = call_llm(system_prompt, user_prompt, provider, model)
    
    return response


def should_show_journey_button(user_query: str, response_text: str) -> bool:
    """
    Determines if a journey navigation button should be shown based on the query and response.
    
    The button should appear when the AI is providing guidance about:
    - Next steps in the journey
    - Current position in the pathway
    - Progress or status updates
    - What to do next
    
    Args:
        user_query: The patient's original question
        response_text: The AI's response text
    
    Returns:
        True if button should be shown, False otherwise
    """
    # Keywords that indicate journey/next steps guidance
    journey_keywords = [
        'next step', 'next steps', 'where you are', 'your journey', 'pathway',
        'stage', 'progress', 'current', 'what to do', 'should do', 'need to',
        'checklist', 'evaluation', 'referral', 'transplant journey', 'journey',
        'position', 'status', 'where are you', 'where am i', 'what stage'
    ]
    
    # Combine query and response for analysis
    combined_text = (user_query + ' ' + response_text).lower()
    
    # Check if any journey keywords appear
    for keyword in journey_keywords:
        if keyword in combined_text:
            return True
    
    return False


async def get_ai_response_stream(patient_id: str, user_query: str, device_id: str, provider: str = "openai", model: str = "gpt-5.1"):
    """
    Main function to get streaming AI response for a patient query (async)
    
    Args:
        patient_id: Patient ID
        user_query: Patient's question
        device_id: Device ID to get patient data
        provider: LLM provider to use
        model: Model name to use
    
    Yields:
        Tuples of (chunk_type, data) where chunk_type is 'text' or 'metadata'
        - 'text' chunks contain response text
        - 'metadata' chunk contains button info (sent once at the end)
    """
    # Build patient context
    context = build_patient_context(patient_id, device_id)
    pathway_stage = context.get("pathway_stage")
    
    # Build prompts
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(user_query, context)
    
    # Collect full response text to determine if button should be shown
    full_response = ""
    
    # Call LLM with streaming (async)
    async for chunk in call_llm_stream(system_prompt, user_prompt, provider, model):
        full_response += chunk
        yield ('text', chunk)
    
    # After streaming completes, determine if button should be shown
    if should_show_journey_button(user_query, full_response):
        button_metadata = {
            'show_button': True,
            'button_text': 'See where you are',
            'pathway_stage': pathway_stage
        }
        yield ('metadata', button_metadata)

