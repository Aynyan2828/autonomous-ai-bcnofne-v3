from typing import Any, Dict
from .base import LLMProvider

async def get_provider(provider_type: str = "ollama") -> LLMProvider:
    if provider_type == "ollama":
        from .providers.ollama_provider import OllamaProvider
        return OllamaProvider()
    elif provider_type == "openai":
        from .providers.openai_provider import OpenAIProvider
        return OpenAIProvider()
    else:
        raise ValueError(f"Unsupported provider type: {provider_type}")
