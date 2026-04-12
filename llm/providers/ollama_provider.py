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
        self.base_url = base_url or cfg.get("base_url") or os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        self.default_timeout = cfg.get("timeout", 120.0)
        self.max_retries = cfg.get("max_retries", 3)
        self.backoff_factor = cfg.get("backoff_factor", 2.0)
        logger.info(f"OllamaProvider initialized with base_url={self.base_url}")

    async def generate_text(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        task_type = kwargs.get("task_type", "unknown")
        task_cfg = LLMConfig.get_task_config(task_type)
        timeout = kwargs.get("timeout") or task_cfg.get("timeout") or self.default_timeout
        max_retries = kwargs.get("max_retries") or self.max_retries
        
        start_time = time.perf_counter()
        last_error_detail: str = ""
        
        logger.info(f"[OLLAMA_REQUEST] url={self.base_url}/api/chat model={model} task={task_type} timeout={timeout}s")
        
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
                    
                    if response.status_code != 200:
                        error_text = response.text
                        logger.error(f"[OLLAMA_ERROR] status={response.status_code} body={error_text}")
                        raise httpx.HTTPStatusError(f"Ollama returned {response.status_code}", request=response.request, response=response)
                    
                    data = response.json()
                    content = data.get("message", {}).get("content", "").strip()
                    latency_ms = int((time.perf_counter() - start_time) * 1000)
                    
                    if content:
                        logger.info(f"[AI_PROVIDER] requested=ollama selected=ollama model={model} latency={latency_ms}ms attempt={attempt+1}")
                        return content
                    raise ValueError("Empty response content from Ollama")
                    
            except httpx.ConnectError as e:
                last_error_detail = f"ConnectError: Could not reach {self.base_url}. Check if Ollama is running and OLLAMA_HOST is set to 0.0.0.0"
                logger.warning(f"[OLLAMA_ATTEMPT_FAILED] attempt={attempt+1} error={last_error_detail}")
            except httpx.TimeoutException as e:
                last_error_detail = f"TimeoutError: Request to {self.base_url} timed out after {timeout}s"
                logger.warning(f"[OLLAMA_ATTEMPT_FAILED] attempt={attempt+1} error={last_error_detail}")
            except Exception as e:
                last_error_detail = f"{type(e).__name__}: {str(e)}"
                logger.warning(f"[OLLAMA_ATTEMPT_FAILED] attempt={attempt+1} error={last_error_detail}")
            
            if attempt < max_retries - 1:
                wait_time = self.backoff_factor ** attempt
                await asyncio.sleep(wait_time)
            else:
                total_latency = int((time.perf_counter() - start_time) * 1000)
                error_msg = f"Ollama failed after {max_retries} attempts ({total_latency}ms). Last error: {last_error_detail}"
                logger.error(f"[OLLAMA_FINAL_FAILURE] {error_msg}")
                raise Exception(error_msg)

        raise Exception("Unknown error in Ollama generation logic")

    async def embed_text(self, model: str, text: str) -> List[float]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {"model": model, "input": text}
                response = await client.post(f"{self.base_url}/api/embeddings", json=payload)
                if response.status_code != 200:
                     # Fallback to /v1/embeddings if /api/embeddings fails (compatibility)
                     response = await client.post(f"{self.base_url}/v1/embeddings", json=payload)
                response.raise_for_status()
                data = response.json()
                if "embedding" in data: return data["embedding"]
                if "data" in data: return data["data"][0]["embedding"]
                raise ValueError("Unexpected embedding response format")
        except Exception as e:
            logger.error(f"[OLLAMA_EMBED_ERROR] {e}")
            raise

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                success = response.status_code == 200
                if success:
                    logger.info(f"[OLLAMA_HEALTH] OK: {self.base_url}")
                else:
                    logger.warning(f"[OLLAMA_HEALTH] Failed: {self.base_url} status={response.status_code}")
                return success
        except Exception as e:
            logger.warning(f"[OLLAMA_HEALTH] Error connecting to {self.base_url}: {e}")
            return False
