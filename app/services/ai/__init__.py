"""
AI service module

Contains AI/LLM configuration and service logic.
"""

from app.services.ai.config import (
    get_openai_api_key,
    get_openai_client,
    get_default_model,
    is_ai_enabled,
)

from app.services.ai.service import (
    build_patient_context,
    format_context_for_prompt,
    build_system_prompt,
    build_user_prompt,
    call_llm,
    call_llm_stream,
    get_ai_response,
    get_ai_response_stream,
)

__all__ = [
    "get_openai_api_key",
    "get_openai_client",
    "get_default_model",
    "is_ai_enabled",
    "build_patient_context",
    "format_context_for_prompt",
    "build_system_prompt",
    "build_user_prompt",
    "call_llm",
    "call_llm_stream",
    "get_ai_response",
    "get_ai_response_stream",
]

