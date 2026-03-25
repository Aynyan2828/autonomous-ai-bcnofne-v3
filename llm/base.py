from __future__ import annotations
from typing import List, Dict, Any, Optional

class LLMProvider:
    provider_type: str = "base"

    async def generate_text(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        raise NotImplementedError

    async def generate_json(self, model: str, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        raise NotImplementedError

    async def embed_text(self, model: str, text: str) -> List[float]:
        raise NotImplementedError

    async def health_check(self) -> bool:
        raise NotImplementedError
