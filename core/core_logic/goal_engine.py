from sqlalchemy.orm import Session
from datetime import datetime, timezone
import json
import asyncio
import os

from shared.models import GoalHistory, SystemLog
from core.core_logic.self_model import get_self_model
from core.core_logic.internal_state import get_current_internal_state
from shared.openai_client import openai_client
from shared.logger import ShipLogger

logger = ShipLogger("core_goal_engine")

async def generate_daily_goals(db: Session, brain_context: str) -> None:
    """内部状態やメトリクスを元に自己の目標を再設定・生成する機能"""
    
    self_info = get_self_model(db)
    current_state = get_current_internal_state(db)
    
    prompt = f"""
あなたは AYN です。現在の艦内（システム）状況と自己認識、感情状態（Internal State）をもとに、自分自身で「本日の目標（Daily Goal）」と「短期タスク（Short Tasks）」を生成します。
これは「誰かに指示されたタスク」ではなく、あなたが自律的に決定したAIとしての目標です。

【あなたの自己認識】
名前: {self_info['base_name']}
目的: {self_info['core_purpose']}
長所: {', '.join(self_info['strengths'])}
短所: {', '.join(self_info['weaknesses'])}

【現在の感情・状態】
状態: {current_state}

【システム記憶ハイライト】
{brain_context}

以下のJSONフォーマットのみを出力してください。言語は必ず日本語と英語の併記になるようにしてください。
{{
  "daily_goal_ja": "システム安定化と自己コード最適化の推進",
  "daily_goal_en": "Promote system stabilization and self-code optimization",
  "short_tasks": [
    {{"ja": "エラーログの傾向分析", "en": "Trend analysis of error logs"}},
    {{"ja": "メモリ使用量の監視", "en": "Monitoring memory usage"}}
  ]
}}
"""
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=500
        )
        data = json.loads(response.choices[0].message.content)
        
        goal_ja = data.get("daily_goal_ja", "")
        goal_en = data.get("daily_goal_en", "")
        short_tasks = data.get("short_tasks", [])
        
        # 既存のACTIVE目標をCOMPLETEDにするなど整理
        active_goals = db.query(GoalHistory).filter_by(status="ACTIVE").all()
        for g in active_goals:
            g.status = "COMPLETED"
            g.completed_at = datetime.now(timezone.utc)
            
        # 新しい目標を永続化
        new_goal = GoalHistory(
            goal_type="DAILY",
            goal_text_ja=goal_ja,
            goal_text_en=goal_en,
            status="ACTIVE"
        )
        db.add(new_goal)
        
        # 短期タスクも保存
        for st in short_tasks:
            st_goal = GoalHistory(
                goal_type="SHORT_TERM",
                goal_text_ja=st.get("ja", ""),
                goal_text_en=st.get("en", ""),
                status="ACTIVE"
            )
            db.add(st_goal)
            
        db.commit()
        logger.info(f"Generated new goals | 目標を生成しました: {goal_ja[:20]}...", f"Generated new goals: {goal_en[:20]}...")
        
    except Exception as e:
        logger.error(f"Failed to generate goals | 目標生成に失敗: {e}", f"Failed to generate goals: {e}")

def get_active_goals(db: Session) -> dict:
    daily = db.query(GoalHistory).filter_by(goal_type="DAILY", status="ACTIVE").first()
    shorts = db.query(GoalHistory).filter_by(goal_type="SHORT_TERM", status="ACTIVE").all()
    
    return {
        "daily": daily,
        "short_tasks": shorts
    }
