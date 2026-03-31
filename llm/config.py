import os
import yaml
import logging
from typing import Any

logger = logging.getLogger("llm.config")

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "llm_config.yaml")

class LLMConfig:
    _data = {}

    @classmethod
    def load(cls):
        if not os.path.exists(CONFIG_PATH):
            logger.warning(f"LLM config not found at {CONFIG_PATH}, using defaults.")
            return
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cls._data = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load LLM config: {e}")

    @classmethod
    def get_provider_config(cls, provider: str) -> dict:
        if not cls._data: cls.load()
        config = cls._data.get("providers", {}).get(provider, {}).copy()
        
        # Override with environment variables
        if provider == "ollama":
            env_url = os.getenv("OLLAMA_BASE_URL")
            if env_url: config["base_url"] = env_url
        elif provider == "openai":
            env_url = os.getenv("OPENAI_BASE_URL")
            if env_url: config["base_url"] = env_url
            env_key = os.getenv("OPENAI_API_KEY")
            if env_key: config["api_key"] = env_key
            
        return config

    @classmethod
    def get_task_config(cls, task: str) -> dict:
        if not cls._data: cls.load()
        tasks = cls._data.get("tasks", {})
        config = tasks.get(task, tasks.get("default", {})).copy()
        
        # Override model with env (Provider specific or Global)
        # e.g., OLLAMA_MODEL or OPENAI_MODEL
        current_provider = cls.get_global("default_provider", "ollama")
        env_model = os.getenv(f"{current_provider.upper()}_MODEL") or os.getenv("LLM_MODEL")
        if env_model:
            config["model"] = env_model
            
        return config

    @classmethod
    def get_global(cls, key: str, default: Any = None) -> Any:
        if not cls._data: cls.load()
        
        # Override default_provider with env
        if key == "default_provider":
            env_val = os.getenv("DEFAULT_LLM_PROVIDER")
            if env_val: return env_val
            
        return cls._data.get(key, default)

LLMConfig.load()
