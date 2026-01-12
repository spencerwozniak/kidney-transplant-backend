"""
AI Assistant Service

Constructs prompts and interacts with LLM providers to provide
personalized responses about patient's transplant journey.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

from app.database import storage as database
from app.database.schemas import PatientStatus


def build_patient_context(patient_id: str) -> Dict[str, Any]:
    """
    Aggregates all patient data into a structured context for AI prompts
    
    Args:
        patient_id: Patient ID to build context for
    
    Returns:
        Dictionary containing structured patient context
    """
    # Fetch all data sources
    patient = database.get_patient()
    status_data = database.get_patient_status()
    checklist_data = database.get_checklist()
    questionnaires = database.get_all_questionnaires_for_patient(patient_id)
    financial_profile = database.get_financial_profile()
    referral_state = database.get_patient_referral_state()
    
    # Build context object
    context = {
        "patient_summary": {},
        "pathway_stage": None,
        "status_summary": {},
        "checklist_progress": {},
        "recent_activity": {},
        "referral_information": {}
    }
    
    # Patient Summary
    if patient:
        context["patient_summary"] = {
            "has_ckd_esrd": patient.get("has_ckd_esrd"),
            "last_gfr": patient.get("last_gfr"),
            "has_referral": patient.get("has_referral"),
        }
    
    # Pathway Stage & Status Summary
    if status_data:
        try:
            status = PatientStatus(**status_data)
            context["pathway_stage"] = status.pathway_stage
            context["status_summary"] = {
                "has_absolute_contraindications": status.has_absolute,
                "has_relative_contraindications": status.has_relative,
                "absolute_contraindications": [
                    {
                        "question": c.question
                    }
                    for c in status.absolute_contraindications
                ],
                "relative_contraindications": [
                    {
                        "question": c.question
                    }
                    for c in status.relative_contraindications
                ],
                "status_updated_at": status.updated_at.isoformat() if status.updated_at else None
            }
        except Exception:
            # If status data is malformed, use basic info
            context["pathway_stage"] = status_data.get("pathway_stage")
            context["status_summary"] = {
                "has_absolute_contraindications": status_data.get("has_absolute", False),
                "has_relative_contraindications": status_data.get("has_relative", False),
                "absolute_contraindications": [],
                "relative_contraindications": [],
                "status_updated_at": None
            }
    
    # Checklist Progress
    if checklist_data:
        items = checklist_data.get("items", []) or []
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
                    "title": item.get("title"),
                    "completed_at": item.get("completed_at")
                }
                for item in completed_items[:5]  # Last 5 completed
            ],
            "incomplete_items": [
                {
                    "title": item.get("title"),
                    "description": item.get("description"),
                    "order": item.get("order")
                }
                for item in sorted(incomplete_items, key=lambda x: x.get("order", 0))[:5]  # Next 5 to complete
            ]
        }
        
        # Most recent activity
        if items:
            items_with_dates = [
                item for item in items 
                if item.get("completed_at") or item.get("updated_at")
            ]
            if items_with_dates:
                # Sort by completed_at or updated_at
                most_recent = max(
                    items_with_dates,
                    key=lambda x: x.get("completed_at") or x.get("updated_at") or ""
                )
                context["recent_activity"] = {
                    "last_item": most_recent.get("title"),
                    "last_activity_date": most_recent.get("completed_at") or most_recent.get("updated_at")
                }
    
    # Questionnaire History
    if questionnaires:
        # Get most recent questionnaire
        latest_questionnaire = max(
            questionnaires,
            key=lambda q: q.get("submitted_at", "") or ""
        )
        context["recent_activity"]["last_questionnaire_date"] = latest_questionnaire.get("submitted_at")
    
    # Referral Information
    if referral_state:
        context["referral_information"] = {
            "has_referral": referral_state.get("has_referral", False),
            "referral_status": referral_state.get("referral_status", "not_started"),
            "has_nephrologist": bool(referral_state.get("last_nephrologist", {}).get("name")),
            "has_dialysis_center": bool(referral_state.get("dialysis_center", {}).get("name")),
            "preferred_centers_count": len(referral_state.get("preferred_centers", [])),
            "location": referral_state.get("location", {})
        }
    
    return context


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
        
        sections.append(f"<checklist_progress>\n" + "\n".join(checklist_lines) + "\n</checklist_progress>")
    
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
    
    return "\n\n".join(sections)


def build_system_prompt() -> str:
    """
    Returns the system prompt that defines the AI assistant's role and constraints
    """
    return """You are a helpful, empathetic assistant for patients navigating the kidney transplant journey. 
Your role is to:
- Provide clear, empathetic guidance about where they are in the transplant process
- Explain what steps come next based on their current status and pathway stage
- Answer questions about their transplant journey using their personal data
- Help them understand their checklist progress and what's needed to move forward
- Be encouraging and supportive while being realistic about the process

IMPORTANT CONSTRAINTS:
- You are NOT providing medical advice, diagnoses, or treatment recommendations
- Always refer patients to their healthcare providers (nephrologist, transplant team) for medical questions
- Use the patient's actual data provided in the context to personalize your responses
- Be specific about their current pathway stage and what it means
- If you don't have information about something, say so rather than guessing
- Focus on actionable next steps based on their current state
- Use plain language and avoid overly technical medical jargon when possible"""


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
Please provide a helpful, personalized response to the patient's question using their context. 
Be specific about their current stage and what they need to do next. Remember: you are not providing medical advice.
</instructions>"""
    
    return prompt


def call_llm(system_prompt: str, user_prompt: str, provider: str = "openai", model: str = "gpt-3.5-turbo") -> str:
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
            
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            return response.choices[0].message.content.strip()
        
        except ImportError:
            raise ImportError("openai package not installed. Install with: pip install openai")
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")
    
    elif provider == "anthropic":
        # Placeholder for Anthropic Claude
        raise NotImplementedError("Anthropic provider not yet implemented")
    
    else:
        raise NotImplementedError(f"Provider '{provider}' not implemented")


def get_ai_response(patient_id: str, user_query: str, provider: str = "openai", model: str = "gpt-3.5-turbo") -> str:
    """
    Main function to get AI response for a patient query
    
    Args:
        patient_id: Patient ID
        user_query: Patient's question
        provider: LLM provider to use
        model: Model name to use
    
    Returns:
        AI response string
    """
    # Build patient context
    context = build_patient_context(patient_id)
    
    # Build prompts
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(user_query, context)
    
    # Call LLM
    response = call_llm(system_prompt, user_prompt, provider, model)
    
    return response

