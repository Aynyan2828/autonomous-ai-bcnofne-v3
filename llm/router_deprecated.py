import os
from typing import Optional

class ModelRouter:
    @staticmethod
    def get_model(task_type: str) -> str:
        """タスクタイプ（chat, summary, code, embed）に応じたモデル名を返す"""
        if task_type == "chat":
            return os.getenv("MODEL_CHAT", "qwen2.5:14b")
        elif task_type == "summary":
            return os.getenv("MODEL_SUMMARY", "qwen2.5:14b")
        elif task_type == "code":
            return os.getenv("MODEL_CODE", "qwen2.5-coder:14b")
        elif task_type == "embed":
            return os.getenv("MODEL_EMBED", "bge-m3")
        elif task_type == "fallback":
            return os.getenv("MODEL_FALLBACK", "gemma3:2b")
        else:
            return os.getenv("MODEL_CHAT", "qwen2.5:14b")
