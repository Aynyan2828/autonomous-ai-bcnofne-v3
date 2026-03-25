from __future__ import annotations

import json
from typing import Any


def try_parse_json(raw_text: str) -> dict[str, Any]:
    return json.loads(raw_text)


def strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        # ```json { ... } ``` のような形式に対応
        lines = text.splitlines()
        if len(lines) >= 3:
            # 言語指定行と閉じブロックを除去
            return "\n".join(lines[1:-1]).strip()
    return text


def clean_json_string(text: str) -> str:
    """JSON以外の文字が混ざっている場合に抽出を試みる"""
    text = strip_code_fence(text)
    
    # 最初と最後の { } を探す
    try:
        start_idx = text.index("{")
        end_idx = text.rindex("}")
        return text[start_idx : end_idx + 1]
    except ValueError:
        return text


def parse_or_none(text: str) -> dict[str, Any] | None:
    # 段階的に試行
    try:
        return json.loads(text.strip())
    except:
        pass
        
    try:
        cleaned = clean_json_string(text)
        return json.loads(cleaned)
    except:
        return None
