from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class LLMProvider(ABC):
    @abstractmethod
    async def generate_text(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        """テキスト生成"""
        raise NotImplementedError

    @abstractmethod
    async def generate_json(self, model: str, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """JSON構造化データの生成 (自動修復付きを想定)"""
        raise NotImplementedError

    @abstractmethod
    async def embed_text(self, model: str, text: str) -> List[float]:
        """テキストのベクトル化"""
        raise NotImplementedError

    @abstractmethod
    async def summarize_long_text(self, model: str, text: str, max_summary_length: int = 500) -> str:
        """長文を分割して要約する"""
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        """プロバイダーの生存確認"""
        raise NotImplementedError
