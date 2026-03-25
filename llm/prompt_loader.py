from __future__ import annotations

import os
from pathlib import Path
from typing import Any
import yaml


class PromptLoader:
    def __init__(self, prompts_dir: str = None) -> None:
        # デフォルトはプロジェクトルートの prompts
        if prompts_dir is None:
            base_dir = Path(__file__).parent.parent
            self.prompts_dir = base_dir / "prompts"
        else:
            self.prompts_dir = Path(prompts_dir)
            
        self.manifest_path = self.prompts_dir / "manifest.yaml"
        self._manifest_cache: dict[str, Any] | None = None
        self._text_cache: dict[str, str] = {}

    def load_manifest(self) -> dict[str, Any]:
        if self._manifest_cache is None:
            if not self.manifest_path.exists():
                raise FileNotFoundError(f"Manifest not found: {self.manifest_path}")
            with self.manifest_path.open("r", encoding="utf-8") as f:
                self._manifest_cache = yaml.safe_load(f)
        return self._manifest_cache

    def load_text(self, relative_path: str) -> str:
        if relative_path in self._text_cache:
            return self._text_cache[relative_path]

        full_path = self.prompts_dir / relative_path
        if not full_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {full_path}")
            
        text = full_path.read_text(encoding="utf-8").strip()
        self._text_cache[relative_path] = text
        return text

    def render(self, template: str, variables: dict[str, Any]) -> str:
        rendered = template
        for key, value in variables.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
        return rendered

    def get_task_prompts(self, task_type: str, variables: dict[str, Any]) -> dict[str, str]:
        manifest = self.load_manifest()
        if task_type not in manifest["tasks"]:
            raise ValueError(f"Unknown task type: {task_type}")
            
        task = manifest["tasks"][task_type]

        system_prompt = self.load_text(task["system_prompt"])
        user_prompt = self.load_text(task["user_prompt"])

        return {
            "system": self.render(system_prompt, variables),
            "user": self.render(user_prompt, variables),
            "output_mode": task["output_mode"],
            "retry_strategy": task["retry_strategy"],
        }
