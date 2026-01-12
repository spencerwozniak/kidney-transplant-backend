"""
AI Configuration

Handles configuration for AI/LLM providers including API keys and client setup.
"""
import os
from typing import Optional
from pathlib import Path
from openai import OpenAI

# Load environment variables from .env file
# This ensures .env is loaded regardless of how the app is started
try:
    from dotenv import load_dotenv
    # Get the project root directory (parent of app/)
    project_root = Path(__file__).parent.parent.parent.parent
    env_path = project_root / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        # Debug: Check if API key was loaded (without exposing the key)
        api_key_loaded = os.getenv("OPENAI_API_KEY") is not None
        if api_key_loaded:
            print(f"[AI Config] .env file loaded from {env_path}, OPENAI_API_KEY found")
        else:
            print(f"[AI Config] .env file loaded from {env_path}, but OPENAI_API_KEY not found")
    else:
        print(f"[AI Config] Warning: .env file not found at {env_path}")
except ImportError:
    # python-dotenv not installed, skip loading .env
    print("[AI Config] Warning: python-dotenv not installed, .env file will not be loaded")
except Exception as e:
    print(f"[AI Config] Error loading .env file: {e}")


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
    return os.getenv("OPENAI_MODEL", "gpt-4o")


def is_ai_enabled() -> bool:
    """
    Check if AI features are enabled (API key configured)
    
    Returns:
        True if AI is enabled, False otherwise
    """
    return get_openai_api_key() is not None

