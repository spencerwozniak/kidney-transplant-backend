"""
AI Assistant API endpoints

Provides chat/query interface for AI assistant to answer questions
about patient's transplant journey.
"""
from fastapi import APIRouter, HTTPException, Body, Request
from fastapi.responses import StreamingResponse
from typing import Optional
from pydantic import BaseModel, Field
import json

from app.database import storage as database
from app.services.ai.service import get_ai_response, get_ai_response_stream, build_patient_context
from app.services.ai.config import is_ai_enabled
from app.api.utils import get_device_id


router = APIRouter()


class AIQueryRequest(BaseModel):
    """Request model for AI assistant query"""
    query: str              = Field(..., description="Patient's question or query")
    provider: Optional[str] = Field(default="openai", description="LLM provider to use")
    model: Optional[str]    = Field(default="gpt-5.1", description="Model name to use (e.g., gpt-5.1, gpt-5.1-mini, gpt-4-turbo, gpt-5 when available)")


class AIQueryResponse(BaseModel):
    """Response model for AI assistant query"""
    response: str         = Field(..., description="AI assistant's response")
    context_summary: dict = Field(..., description="Summary of patient context used")


@router.post("/ai-assistant/query", response_model=AIQueryResponse)
async def query_ai_assistant(request_body: AIQueryRequest, request: Request):
    """
    Query the AI assistant about patient's transplant journey
    
    Uses patient data to provide personalized responses about:
    - Current pathway stage and progress
    - Next steps and checklist items
    - Contraindications and status
    - Referral information
    - General questions about transplant journey
    """
    device_id = get_device_id(request)
    # Check if AI is enabled
    if not is_ai_enabled():
        raise HTTPException(
            status_code=503,
            detail="AI assistant is not configured. Please set OPENAI_API_KEY environment variable."
        )
    
    # Verify patient exists
    patient = database.get_patient(device_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    patient_id = patient.get('id')
    
    try:
        # Get AI response
        response = get_ai_response(
            patient_id=patient_id,
            user_query=request_body.query,
            device_id=device_id,
            provider=request_body.provider or "openai",
            model=request_body.model or "gpt-5.1"
        )
        
        # Build context summary for response (simplified version)
        context = build_patient_context(patient_id, device_id)
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
async def get_ai_context(request: Request):
    """
    Get the patient context that would be used for AI prompts
    
    Useful for debugging or understanding what data the AI has access to.
    """
    device_id = get_device_id(request)
    # Verify patient exists
    patient = database.get_patient(device_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    patient_id = patient.get('id')
    
    # Build and return context
    context = build_patient_context(patient_id, device_id)
    
    return {
        "patient_id": patient_id,
        "context": context
    }


@router.post("/ai-assistant/query/stream")
async def query_ai_assistant_stream(request_body: AIQueryRequest, request: Request):
    """
    Query the AI assistant with streaming response
    
    Returns a streaming response where text chunks are sent as they are generated.
    Each chunk is sent as a JSON line: {"chunk": "text chunk"}
    """
    device_id = get_device_id(request)
    # Check if AI is enabled
    if not is_ai_enabled():
        raise HTTPException(
            status_code=503,
            detail="AI assistant is not configured. Please set OPENAI_API_KEY environment variable."
        )
    
    # Verify patient exists
    patient = database.get_patient(device_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    patient_id = patient.get('id')
    
    async def generate():
        try:
            print(f"[AI Stream] Starting stream for query: {request_body.query[:50]}...")
            chunk_count = 0
            button_metadata = None
            
            # Stream AI response (async for proper event loop yielding)
            async for chunk_type, chunk_data in get_ai_response_stream(
                patient_id=patient_id,
                user_query=request_body.query,
                device_id=device_id,
                provider=request_body.provider or "openai",
                model=request_body.model or "gpt-5.1"
            ):
                if chunk_type == 'text':
                    chunk_count += 1
                    # Send each text chunk as JSON
                    chunk_json = f"data: {json.dumps({'chunk': chunk_data})}\n\n"
                    print(f"[AI Stream] Yielding chunk {chunk_count}: {chunk_data[:20]}...")
                    yield chunk_json.encode('utf-8')
                elif chunk_type == 'metadata':
                    # Store button metadata to send after completion
                    button_metadata = chunk_data
            
            print(f"[AI Stream] Completed, sent {chunk_count} chunks")
            
            # Send button metadata if available
            if button_metadata:
                metadata_json = f"data: {json.dumps({'button': button_metadata})}\n\n"
                yield metadata_json.encode('utf-8')
            
            # Send completion signal
            yield f"data: {json.dumps({'done': True})}\n\n".encode('utf-8')
        
        except ValueError as e:
            print(f"[AI Stream] ValueError: {str(e)}")
            error_data = json.dumps({'error': str(e)})
            yield f"data: {error_data}\n\n".encode('utf-8')
        except AttributeError as e:
            import traceback
            error_detail = f"Data structure error: {str(e)}. This may indicate missing or malformed patient data."
            print(f"[AI API Error] {error_detail}\n{traceback.format_exc()}")
            error_data = json.dumps({'error': error_detail})
            yield f"data: {error_data}\n\n".encode('utf-8')
        except Exception as e:
            import traceback
            error_detail = f"AI service error: {str(e)}"
            print(f"[AI API Error] {error_detail}\n{traceback.format_exc()}")
            error_data = json.dumps({'error': error_detail})
            yield f"data: {error_data}\n\n".encode('utf-8')
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


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

