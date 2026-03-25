import os
import logging
from typing import Optional
from .base import LLMProvider
from .openai_provider import OpenAIProvider
from .ollama_provider import OllamaProvider
from .fallback_provider import FallbackProvider

logger = logging.getLogger("shared.llm")

async def get_llm_provider(backend: Optional[str] = None) -> LLMProvider:
    """環境変数または引数に基づいて LLM プロバイダーのインスタンスを返す"""
    backend = backend or os.getenv("LLM_BACKEND", "local")
    
    if backend == "openai":
        return OpenAIProvider()
    elif backend in ["local", "hybrid"]:
        primary = OllamaProvider()
        fallback = OpenAIProvider()
        return FallbackProvider(primary, fallback)
    else:
        logger.warning(f"Unknown backend '{backend}', falling back to Ollama.")
        return OllamaProvider()

async def get_fallback_provider() -> LLMProvider:
    """メインが落ちた時のためのバックアップ（通常は OpenAI）を返す"""
    return OpenAIProvider()
