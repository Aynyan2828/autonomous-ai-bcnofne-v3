import asyncio
import os
import json
import httpx
import logging
from typing import List, Dict, Any, Optional
from ..base import LLMProvider

logger = logging.getLogger("llm.providers.ollama")

class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        self.timeout = float(os.getenv("LLM_REQUEST_TIMEOUT", "60.0"))

    async def generate_text(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))
        last_error: Optional[Exception] = None
        
        task_type = kwargs.get("task_type", "unknown")
        logger.info(f"Ollama request started: task={task_type}, model={model}, timeout={self.timeout}s")
        
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    payload = {
                        "model": model,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "temperature": kwargs.get("temperature", 0.7),
                            "num_predict": kwargs.get("max_tokens", 1024),
                        },
                    }
                    response = await client.post(f"{self.base_url}/v1/chat/completions", json=payload)
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"].strip()
                    if content:
                        logger.info(f"Ollama request success: task={task_type}, model={model}")
                        return content
                    raise ValueError("Empty response from Ollama")
            except Exception as e:
                last_error = e
                wait_time = (2 ** attempt)
                if attempt < max_retries - 1:
                    logger.warn(f"Ollama attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Ollama all retries failed for task={task_type}: {e}")
        
        if last_error:
            raise last_error
        raise Exception("Unknown error in generate_text")

    async def embed_text(self, model: str, text: str) -> List[float]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {
                "model": model,
                "input": text
            }
            response = await client.post(f"{self.base_url}/v1/embeddings", json=payload)
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except:
            return False
