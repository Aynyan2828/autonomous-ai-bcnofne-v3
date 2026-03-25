import logging
import os
from typing import List, Dict, Any
from ..base import LLMProvider

logger = logging.getLogger("llm.providers.fallback")

class FallbackProvider(LLMProvider):
    def __init__(self, primary: LLMProvider, fallback: LLMProvider):
        self.primary = primary
        self.fallback = fallback
        self.enable_fallback = os.getenv("ENABLE_OPENAI_FALLBACK", "true").lower() == "true"

    async def generate_text(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        try:
            return await self.primary.generate_text(model, messages, **kwargs)
        except Exception as e:
            if not self.enable_fallback:
                raise e
            logger.warning(f"Primary LLM failed: {e}. Falling back to secondary provider.")
            #NOTE: 実際には router で定義された fallback モデルを使うべきだが、
            # 現在のアーキテクチャでは provider レベルでの fallback は暫定的に gpt-4o-mini を使うか、
            # 呼び出し側で再実行させるのが筋。ここでは簡易的にマッピング。
            fallback_model = self._get_fallback_model(model)
            return await self.fallback.generate_text(fallback_model, messages, **kwargs)

    async def embed_text(self, model: str, text: str) -> List[float]:
        try:
            return await self.primary.embed_text(model, text)
        except Exception as e:
            if not self.enable_fallback:
                raise e
            logger.warning(f"Primary LLM Embed failed: {e}. Falling back to secondary provider.")
            fallback_model = "text-embedding-3-small"
            return await self.fallback.embed_text(fallback_model, text)

    async def health_check(self) -> bool:
        return await self.primary.health_check()

    def _get_fallback_model(self, model: str) -> str:
        if "coder" in model:
            return "gpt-4o"
        return "gpt-4o-mini"
