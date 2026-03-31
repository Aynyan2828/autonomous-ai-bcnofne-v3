import asyncio
import os
import json
import httpx
import logging
import time
from typing import List, Dict, Any, Optional
from ..base import LLMProvider
from ..config import LLMConfig

logger = logging.getLogger("llm.providers.ollama")

class OllamaProvider(LLMProvider):
    provider_type: str = "ollama"

    def __init__(self, base_url: Optional[str] = None):
        cfg = LLMConfig.get_provider_config("ollama")
        self.base_url = base_url or cfg.get("base_url", "http://ollama:11434")
        self.default_timeout = cfg.get("timeout", 60.0)
        self.max_retries = cfg.get("max_retries", 3)
        self.backoff_factor = cfg.get("backoff_factor", 2.0)

    async def generate_text(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        task_type = kwargs.get("task_type", "unknown")
        task_cfg = LLMConfig.get_task_config(task_type)
        timeout = kwargs.get("timeout") or task_cfg.get("timeout") or self.default_timeout
        max_retries = kwargs.get("max_retries") or self.max_retries
        
        start_time = time.perf_counter()
        last_error: Optional[Exception] = None
        
        logger.info(f"[Ollama] Request started: task={task_type}, model={model}, timeout={timeout}s")
        
        for attempt in range(max_retries):
            attempt_start = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    payload = {
                        "model": model,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "temperature": kwargs.get("temperature", 0.7),
                            "num_predict": kwargs.get("max_tokens", 2048),
                        },
                    }
                    response = await client.post(f"{self.base_url}/api/chat", json=payload)
                    response.raise_for_status()
                    data = response.json()
                    
                    content = data["message"]["content"].strip()
                    latency_ms = int((time.perf_counter() - start_time) * 1000)
                    
                    if content:
                        logger.info(f"[Ollama] Request success: task={task_type}, model={model}, latency={latency_ms}ms, attempt={attempt+1}")
                        return content
                    raise ValueError("Empty response from Ollama")
                    
            except Exception as e:
                last_error = e
                latency_ms = int((time.perf_counter() - attempt_start) * 1000)
                wait_time = self.backoff_factor ** attempt
                
                logger.warning(f"[Ollama] Attempt {attempt+1} failed ({latency_ms}ms): {e}")
                
                if attempt < max_retries - 1:
                    logger.info(f"[Ollama] Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    total_latency = int((time.perf_counter() - start_time) * 1000)
                    logger.error(f"[Ollama] All retries failed for task={task_type} ({total_latency}ms): {e}")
        
        if last_error:
            raise last_error
        raise Exception("Unknown error in Ollama generation")

    async def embed_text(self, model: str, text: str) -> List[float]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {"model": model, "input": text}
                response = await client.post(f"{self.base_url}/v1/embeddings", json=payload)
                response.raise_for_status()
                return response.json()["data"][0]["embedding"]
        except Exception as e:
            logger.error(f"Ollama embedding failed: {e}")
            raise

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except:
            return False
