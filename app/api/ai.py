"""
AI Assistant API endpoints

Provides chat/query interface for AI assistant to answer questions
about patient's transplant journey.
"""
from fastapi import APIRouter, HTTPException, Body
from typing import Optional
from pydantic import BaseModel, Field

from app.database import storage as database
from app.services.ai.service import get_ai_response, build_patient_context
from app.services.ai.config import is_ai_enabled


router = APIRouter()


class AIQueryRequest(BaseModel):
    """Request model for AI assistant query"""
    query: str              = Field(..., description="Patient's question or query")
    provider: Optional[str] = Field(default="openai", description="LLM provider to use")
    model: Optional[str]    = Field(default="gpt-5.1", description="Model name to use")


class AIQueryResponse(BaseModel):
    """Response model for AI assistant query"""
    response: str         = Field(..., description="AI assistant's response")
    context_summary: dict = Field(..., description="Summary of patient context used")


@router.post("/ai-assistant/query", response_model=AIQueryResponse)
async def query_ai_assistant(request: AIQueryRequest):
    """
    Query the AI assistant about patient's transplant journey
    
    Uses patient data to provide personalized responses about:
    - Current pathway stage and progress
    - Next steps and checklist items
    - Contraindications and status
    - Referral information
    - General questions about transplant journey
    
    CURRENT: Single patient assumption, uses current patient's data
    """
    # Check if AI is enabled
    if not is_ai_enabled():
        raise HTTPException(
            status_code=503,
            detail="AI assistant is not configured. Please set OPENAI_API_KEY environment variable."
        )
    
    # Verify patient exists
    patient = database.get_patient()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    patient_id = patient.get('id')
    
    try:
        # Get AI response
        response = get_ai_response(
            patient_id=patient_id,
            user_query=request.query,
            provider=request.provider or "openai",
            model=request.model or "gpt-5.1"
        )
        
        # Build context summary for response (simplified version)
        context = build_patient_context(patient_id)
        context_summary = {
            "pathway_stage": context.get("pathway_stage"),
            "checklist_completion": context.get("checklist_progress", {}).get("completion_percentage"),
            "has_referral": context.get("referral_information", {}).get("has_referral")
        }
        
        return AIQueryResponse(
            response=response,
            context_summary=context_summary
        )
    
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except AttributeError as e:
        # Handle NoneType attribute errors more gracefully
        import traceback
        error_detail = f"Data structure error: {str(e)}. This may indicate missing or malformed patient data."
        print(f"[AI API Error] {error_detail}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_detail)
    except Exception as e:
        import traceback
        error_detail = f"AI service error: {str(e)}"
        print(f"[AI API Error] {error_detail}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_detail)


@router.get("/ai-assistant/context")
async def get_ai_context():
    """
    Get the patient context that would be used for AI prompts
    
    Useful for debugging or understanding what data the AI has access to.
    CURRENT: Single patient assumption
    """
    # Verify patient exists
    patient = database.get_patient()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    patient_id = patient.get('id')
    
    # Build and return context
    context = build_patient_context(patient_id)
    
    return {
        "patient_id": patient_id,
        "context": context
    }


@router.get("/ai-assistant/status")
async def get_ai_status():
    """
    Check if AI assistant is enabled and configured
    
    Returns status information about AI configuration
    """
    enabled = is_ai_enabled()
    
    status = {
        "enabled": enabled,
        "provider": "openai" if enabled else None,
        "message": "AI assistant is configured and ready" if enabled else "AI assistant is not configured. Set OPENAI_API_KEY to enable."
    }
    
    return status

