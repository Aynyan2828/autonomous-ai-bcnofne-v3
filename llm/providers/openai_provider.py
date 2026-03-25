import os
import httpx
import logging
from typing import List, Dict, Any, Optional
from ..base import LLMProvider
from ..config import LLMConfig

logger = logging.getLogger("llm.providers.openai")

class OpenAIProvider(LLMProvider):
    provider_type: str = "openai"

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        cfg = LLMConfig.get_provider_config("openai")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or cfg.get("base_url", "https://api.openai.com/v1")
        self.timeout = cfg.get("timeout", 30.0)

    async def generate_text(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        if not self.api_key:
            raise ValueError("OpenAI API Key is not set.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2048)
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"].strip()
            if content:
                return content
            raise ValueError("Empty response from OpenAI")

    async def embed_text(self, model: str, text: str) -> List[float]:
        if not self.api_key:
            raise ValueError("OpenAI API Key is not set.")
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {"model": model, "input": text}
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{self.base_url}/embeddings", headers=headers, json=payload)
            response.raise_for_status()
            return response.json()["data"][0]["embedding"]

    async def health_check(self) -> bool:
        return bool(self.api_key)
