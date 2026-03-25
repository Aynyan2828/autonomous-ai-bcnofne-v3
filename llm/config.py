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
        return cls._data.get("providers", {}).get(provider, {})

    @classmethod
    def get_task_config(cls, task: str) -> dict:
        if not cls._data: cls.load()
        tasks = cls._data.get("tasks", {})
        return tasks.get(task, tasks.get("default", {}))

    @classmethod
    def get_global(cls, key: str, default: Any = None) -> Any:
        if not cls._data: cls.load()
        return cls._data.get(key, default)

LLMConfig.load()
