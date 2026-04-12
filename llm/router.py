from __future__ import annotations

import os
import yaml
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("llm.router")

class ModelRouter:
    def __init__(self, config_path: str = None) -> None:
        if config_path is None:
            base_dir = Path(__file__).parent.parent
            self.config_path = base_dir / "config" / "llm_models.yaml"
        else:
            self.config_path = Path(config_path)
            
        self._config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self):
        if not self.config_path.exists():
            raise FileNotFoundError(f"Model config not found: {self.config_path}")
        with self.config_path.open("r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f)

    def get_model(self, task_type: str) -> str:
        models = self._config.get("models", {})
        task_config = models.get(task_type, models.get("chat", {}))
        return task_config.get("primary", "qwen2.5:7b")

    def get_fallback_model(self, task_type: str) -> str:
        models = self._config.get("models", {})
        task_config = models.get(task_type, models.get("chat", {}))
        return task_config.get("fallback", "gpt-4o-mini")

    async def get_provider(self) -> Any:
        # この中身は factory.py 的な役割を統合
        from .providers.ollama_provider import OllamaProvider
        from .providers.openai_provider import OpenAIProvider
        from .providers.fallback_provider import FallbackProvider
        
        backend = self._config.get("backend", "local")
        local_cfg = self._config.get("providers", {}).get("local", {})
        openai_cfg = self._config.get("providers", {}).get("openai", {})
        
        # OLLAMA_BASE_URL 環境変数を最優先にする
        ollama_url = os.getenv("OLLAMA_BASE_URL") or local_cfg.get("base_url", "http://ollama:11434")
        
        local = OllamaProvider(base_url=ollama_url)
        openai = OpenAIProvider(api_key=os.getenv(openai_cfg.get("api_key_env", "OPENAI_API_KEY")))
        
        if backend == "local":
            return local
        elif backend == "openai":
            return openai
        else:
            return FallbackProvider(primary=local, fallback=openai)

_router_instance: Optional[ModelRouter] = None

async def get_model_router() -> ModelRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = ModelRouter()
    return _router_instance

async def get_llm_executor() -> Any:
    from .executor import LLMExecutor
    router = await get_model_router()
    provider = await router.get_provider()
    return LLMExecutor(provider=provider)
