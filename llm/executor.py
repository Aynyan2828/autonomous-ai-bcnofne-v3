from __future__ import annotations

import logging
import asyncio
import time
from typing import Any, Type, Dict, Optional

from pydantic import BaseModel, ValidationError

from llm.prompt_loader import PromptLoader
from llm.json_repair import parse_or_none
from llm.router import ModelRouter
from llm.config import LLMConfig

logger = logging.getLogger("llm.executor")

class LLMExecutor:
    def __init__(self, provider: Any = None, repair_provider: Any | None = None) -> None:
        self.provider = provider
        self.repair_provider = repair_provider
        self.prompt_loader = PromptLoader()
        self._router_cache: Optional[ModelRouter] = None

    async def _get_router(self) -> ModelRouter:
        if self._router_cache is None:
            from .router import get_model_router
            self._router_cache = await get_model_router()
        return self._router_cache

    async def _get_provider(self, router: ModelRouter) -> Any:
        """優先順位: 1.明示指定, 2.Router定義, 3.Configデフォルト"""
        if self.provider:
            return self.provider
        
        # Router からプロバイダ取得を試みる（既存実装互換）
        try:
            return await router.get_provider()
        except:
            # フォールバックとして Config から取得
            from .factory import get_provider
            default_p = LLMConfig.get_global("default_provider", "ollama")
            return await get_provider(default_p)

    async def execute_text(self, task_type: str, variables: dict[str, Any]) -> str:
        prompts = self.prompt_loader.get_task_prompts(task_type, variables)
        router = await self._get_router()
        model = router.get_model(task_type)
        provider = await self._get_provider(router)
        
        messages = [
            {"role": "system", "content": prompts["system"]},
            {"role": "user", "content": prompts["user"]}
        ]
        
        try:
            res = await provider.generate_text(
                model=model,
                messages=messages,
                task_type=task_type
            )
            # 成功したら、もしフォールバック中やった場合はモードを元に戻す（再試行ベース）
            from llm.status import record_mode_switch, _get_state
            db = SessionLocal()
            current_active = _get_state(db, "active_ai_mode", provider.provider_type)
            if current_active == "openai" and provider.provider_type != "openai":
                 record_mode_switch(db, "openai", provider.provider_type, f"Recovered from {task_type}")
            db.close()
            return res
        except Exception as e:
            if LLMConfig.get_global("fallback_enabled", True) and provider.provider_type != "openai":
                logger.warning(f"Task {task_type} failed on {provider.provider_type}. Falling back to OpenAI. Error: {e}")
                from llm.status import record_mode_switch
                db = SessionLocal()
                record_mode_switch(db, provider.provider_type, "openai", f"Fallback due to {task_type} error: {str(e)[:100]}")
                db.close()

                from .factory import get_provider
                fallback_provider = await get_provider("openai")
                return await fallback_provider.generate_text(
                    model="gpt-4o-mini", # 固定または設定から
                    messages=messages,
                    task_type=task_type
                )
            raise

    async def execute_json(
        self,
        task_type: str,
        variables: dict[str, Any],
        schema: Type[BaseModel] = None, # スキーマなし（Dict）も許容
    ) -> Any:
        prompts = self.prompt_loader.get_task_prompts(task_type, variables)
        router = await self._get_router()
        model = router.get_model(task_type)
        provider = await self._get_provider(router)
        
        # 7B向けにJSON出力のヒントを強化
        user_prompt = prompts["user"]
        if "JSON" not in user_prompt.upper():
            user_prompt += "\n\nIMPORTANT: Output valid JSON only."
            
        messages = [
            {"role": "system", "content": prompts["system"]},
            {"role": "user", "content": user_prompt}
        ]
 
        from llm.status import record_mode_switch, _get_state
        raw = ""
        try:
            raw = await provider.generate_text(
                model=model,
                messages=messages,
                task_type=task_type
            )
            # 成功時の復帰チェック
            db = SessionLocal()
            current_active = _get_state(db, "active_ai_mode", provider.provider_type)
            if current_active == "openai" and provider.provider_type != "openai":
                 record_mode_switch(db, "openai", provider.provider_type, f"Recovered from JSON task {task_type}")
            db.close()
        except Exception as e:
            if LLMConfig.get_global("fallback_enabled", True) and provider.provider_type != "openai":
                logger.warning(f"JSON Task {task_type} failed on {provider.provider_type}. Falling back to OpenAI.")
                db = SessionLocal()
                record_mode_switch(db, provider.provider_type, "openai", f"Fallback due to JSON {task_type} error: {str(e)[:100]}")
                db.close()

                from .factory import get_provider
                fallback_provider = await get_provider("openai")
                raw = await fallback_provider.generate_text(
                    model="gpt-4o-mini",
                    messages=messages,
                    task_type=task_type
                )
            else:
                raise

        parsed = parse_or_none(raw)
        if parsed is not None:
            if schema:
                try:
                    return schema.model_validate(parsed)
                except ValidationError as e:
                    logger.warning(f"Validation error for {task_type}: {e}. Attempting repair.")
            else:
                return parsed

        # Repair プロンプトによる修復
        repair_provider = self.repair_provider or provider
        if raw:
            repair_variables = {"input_text": raw}
            repair_prompts = self.prompt_loader.get_task_prompts("repair", repair_variables)
            repair_model = router.get_model("repair")
            
            repair_messages = [
                {"role": "system", "content": repair_prompts["system"]},
                {"role": "user", "content": repair_prompts["user"]}
            ]

            repaired_raw = await repair_provider.generate_text(
                model=repair_model,
                messages=repair_messages,
                task_type="repair"
            )

            repaired_parsed = parse_or_none(repaired_raw)
            if repaired_parsed is not None:
                if schema:
                    try:
                        return schema.model_validate(repaired_parsed)
                    except ValidationError as e:
                        logger.error(f"Schema validation failed after repair: {e}")
                        raise e
                return repaired_parsed

        logger.error(f"JSON repair failed for {task_type}. raw={raw!r}")
        raise ValueError(f"JSON repair failed. task={task_type}")

    async def execute_summarization(
        self,
        text: str,
        chunk_size: int = 1800,
        overlap: int = 200,
    ) -> FinalSummaryResult:
        """長文を分割要約し、最終的な統合要約を生成するフロー"""
        from llm.chunking import chunk_text
        from llm.schemas import ChunkSummaryResult, FinalSummaryResult

        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        
        if not chunks:
            return FinalSummaryResult(final_summary="本文が空です。", keywords=[], importance="low")

        if len(chunks) == 1:
            return await self.execute_json(
                task_type="summary",
                variables={"input_text": chunks[0]},
                schema=FinalSummaryResult
            )

        partial_results = []
        for chunk in chunks:
            item = await self.execute_json(
                task_type="chunk_summary",
                variables={"input_text": chunk},
                schema=ChunkSummaryResult,
            )
            partial_results.append(item.chunk_summary)

        final_input = "\n---\n".join(partial_results)

        return await self.execute_json(
            task_type="final_summary",
            variables={"input_text": final_input},
            schema=FinalSummaryResult,
        )
