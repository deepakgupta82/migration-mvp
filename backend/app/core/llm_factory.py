import os, logging
from typing import Any
from .crew import get_llm_class, LLMInitializationError, test_llm_connection  # reuse helper & exception

logger = logging.getLogger(__name__)

def get_llm_and_model():  # identical signature
    provider = os.environ.get("LLM_PROVIDER", "openai").lower()
    try:
        llm = _initialize_provider(provider)
        if llm and test_llm_connection(llm):
            logger.info(f"Successfully initialized LLM with provider: {provider}")
            return llm
        raise Exception(f"LLM connection test failed for provider: {provider}")
    except Exception as e:
        logger.error(f"Failed to initialize {provider}: {e}")
        raise LLMInitializationError(
            f"Failed to initialize LLM provider '{provider}': {str(e)}. Check configuration.")

def _initialize_provider(provider: str):
    from .crew import _initialize_provider as _orig  # delegate to original to avoid duplication for now
    return _orig(provider)

def get_project_llm(project: Any):
    from .crew import get_project_llm as _orig_project
    return _orig_project(project)
