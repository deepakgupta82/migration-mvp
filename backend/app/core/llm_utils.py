"""
Lightweight LLM utilities used by the backend gateway without CrewAI dependencies.
"""

import logging

logger = logging.getLogger(__name__)

_llm_classes = {}


class LLMInitializationError(Exception):
    """Custom exception for LLM initialization failures"""
    pass


def get_llm_class(provider: str):
    """Lazy load LLM classes to improve startup time"""
    if provider not in _llm_classes:
        if provider == 'openai':
            from langchain_openai import ChatOpenAI
            _llm_classes[provider] = ChatOpenAI
        elif provider == 'anthropic':
            from langchain_anthropic import ChatAnthropic
            _llm_classes[provider] = ChatAnthropic
        elif provider in ('google', 'gemini'):
            # Prefer Google Generative AI for Gemini
            from langchain_google_genai import ChatGoogleGenerativeAI
            _llm_classes[provider] = ChatGoogleGenerativeAI
        elif provider == 'ollama':
            from langchain_community.llms import Ollama
            _llm_classes[provider] = Ollama
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
    return _llm_classes[provider]


def test_llm_connection(llm) -> bool:
    """Basic health check to ensure LLM responds."""
    try:
        # Minimal token invocation; some providers may require .invoke
        if hasattr(llm, 'invoke'):
            resp = llm.invoke("ping")
        else:
            # Fallback common call signature
            resp = llm("ping")
        return resp is not None
    except Exception:
        return False
