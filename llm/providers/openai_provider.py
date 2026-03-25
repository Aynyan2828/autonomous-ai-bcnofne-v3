import os
import json
import httpx
import logging
from typing import List, Dict, Any
from openai import AsyncOpenAI
from ..base import LLMProvider

logger = logging.getLogger("llm.providers.openai")

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str = None):
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = AsyncOpenAI(api_key=api_key)

    async def generate_text(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            **kwargs
        )
        await self._report_billing(response, model)
        return response.choices[0].message.content.strip()

    async def generate_json(self, model: str, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            **kwargs
        )
        await self._report_billing(response, model)
        return json.loads(response.choices[0].message.content)

    async def embed_text(self, model: str, text: str) -> List[float]:
        response = await self.client.embeddings.create(
            input=text,
            model=model
        )
        return response.data[0].embedding

    async def health_check(self) -> bool:
        try:
            await self.client.models.list()
            return True
        except:
            return False

    async def _report_billing(self, response, model: str):
        """billing-guard に使用量を報告する"""
        try:
            usage = getattr(response, "usage", None)
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0
            async with httpx.AsyncClient() as client:
                await client.post("http://billing-guard:8002/record",
                                 params={"model": model, "input_tokens": input_tokens, "output_tokens": output_tokens},
                                 timeout=2.0)
        except:
            pass
