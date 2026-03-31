import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from llm.config import LLMConfig
from shared.database import SessionLocal
from shared.models import SystemState, AIModeLog

def get_ai_mode_status() -> Dict[str, Any]:
    """
    現在のAI動作モードの詳細ステータスを返す。
    """
    db = SessionLocal()
    try:
        # 設定上のモード
        configured_provider = LLMConfig.get_global("default_provider", "ollama")
        
        # 実際の使用モード (DBから取得)
        active_mode = _get_state(db, "active_ai_mode", configured_provider)
        fallback_active = active_mode == "openai" and configured_provider != "openai"
        
        # モデル名
        # TODO: 本来は Router から各タスクごとのモデルを取るべきだが、代表的なものを設定から抜く
        local_model = LLMConfig.get_provider_config("ollama").get("model", "llama3")
        openai_model = LLMConfig.get_provider_config("openai").get("model", "gpt-4o-mini")
        
        # キャッシュされた死活情報 (もしあれば)
        local_ai_available = _get_state(db, "local_ai_available", "unknown") == "true"
        openai_available = _get_state(db, "openai_available", "unknown") == "true"
        
        # 最終切替情報
        last_switch_at_raw = _get_state(db, "last_ai_mode_switch_at", None)
        last_switch_reason = _get_state(db, "last_ai_mode_switch_reason", "No switch recorded")
        
        # 日本語ラベル生成
        if fallback_active:
            display_label_ja = "OpenAI (ローカル障害によるフォールバック中)"
            display_label_en = "OpenAI (Fallback due to local failure)"
        elif active_mode == "ollama":
            display_label_ja = f"ローカルAI ({local_model})"
            display_label_en = f"Local AI ({local_model})"
        else:
            display_label_ja = f"クラウドAI ({openai_model})"
            display_label_en = f"Cloud AI ({openai_model})"

        return {
            "configured_mode": configured_provider,
            "active_mode": active_mode,
            "fallback_active": fallback_active,
            "local_model_name": local_model,
            "openai_model_name": openai_model,
            "local_ai_available": local_ai_available,
            "openai_available": openai_available,
            "last_mode_switch_at": last_switch_at_raw,
            "last_mode_switch_reason": last_switch_reason,
            "display_label_ja": display_label_ja,
            "display_label_en": display_label_en
        }
    finally:
        db.close()

def _get_state(db, key: str, default: Any) -> Any:
    state = db.query(SystemState).filter_by(key=key).first()
    return state.value if state else default

def record_mode_switch(db, from_mode: str, to_mode: str, reason: str):
    """
    モード切替をDBに記録し、ログテーブルにも書き込む。
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # 1. system_state の更新
    _set_state(db, "active_ai_mode", to_mode)
    _set_state(db, "last_ai_mode_switch_at", now_iso)
    _set_state(db, "last_ai_mode_switch_reason", reason)
    
    # 2. AIModeLog への記録
    log_entry = AIModeLog(
        from_mode=from_mode,
        to_mode=to_mode,
        reason=reason
    )
    db.add(log_entry)
    db.commit()

def _set_state(db, key: str, value: str):
    state = db.query(SystemState).filter_by(key=key).first()
    if state:
        state.value = value
    else:
        db.add(SystemState(key=key, value=value))
    db.commit()
