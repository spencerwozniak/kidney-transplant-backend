"""
AI Configuration

Handles configuration for AI/LLM providers including API keys and client setup.
"""
import os
from typing import Optional
from openai import OpenAI


def get_openai_api_key() -> Optional[str]:
    """
    Get OpenAI API key from environment variable
    
    Returns:
        API key string or None if not set
    """
    return os.getenv("OPENAI_API_KEY")


def get_openai_client() -> OpenAI:
    """
    Get configured OpenAI client
    
    Returns:
        OpenAI client instance
    
    Raises:
        ValueError: If API key is not configured
    """
    api_key = get_openai_api_key()
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable not set. "
            "Please set it to use the AI assistant feature."
        )
    
    return OpenAI(api_key=api_key)


def get_default_model() -> str:
    """
    Get default model name from environment or use default
    
    Returns:
        Model name string
    """
    return os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")


def is_ai_enabled() -> bool:
    """
    Check if AI features are enabled (API key configured)
    
    Returns:
        True if AI is enabled, False otherwise
    """
    return get_openai_api_key() is not None

