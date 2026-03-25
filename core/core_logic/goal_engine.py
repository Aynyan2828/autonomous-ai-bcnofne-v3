from sqlalchemy.orm import Session
from datetime import datetime, timezone
import json
import asyncio
import os

from shared.models import GoalHistory, SystemLog
from core.core_logic.self_model import get_self_model
from core.core_logic.internal_state import get_current_internal_state
from llm import get_llm_executor
from llm.schemas import GoalResult
from shared.logger import ShipLogger

# LLM プロバイダーの導入

logger = ShipLogger("core_goal_engine")

async def generate_daily_goals(db: Session, brain_context: str) -> None:
    """内部状態やメトリクスを元に自己の目標を再設定・生成する機能"""
    
    self_info = get_self_model(db)
    current_state = get_current_internal_state(db)
    
    # テンプレート化されたプロンプト管理構成経由で目標生成を実行
    try:
        executor = await get_llm_executor()
        
        # テンプレート変数を用意
        variables = {
            "base_name": self_info.get("base_name", "AYN"),
            "core_purpose": self_info.get("core_purpose", "Unknown"),
            "current_state": str(current_state),
            "brain_context": brain_context
        }
        
        from llm.schemas import GoalResult
        result: GoalResult = await executor.execute_json(
            task_type="goal",
            variables=variables,
            schema=GoalResult
        )

        goal_ja = result.daily_goal_ja
        goal_en = result.daily_goal_en
        short_tasks = result.short_tasks

        # 既存のACTIVE目標をCOMPLETEDにするなど整理
        db.query(GoalHistory).filter_by(status="ACTIVE").update({
            "status": "COMPLETED",
            "completed_at": datetime.now(timezone.utc)
        })
            
        # 新しい目標を永続化 (DAILY)
        new_goal = GoalHistory(
            goal_type="DAILY",
            goal_text_ja=goal_ja,
            goal_text_en=goal_en,
            status="ACTIVE"
        )
        db.add(new_goal)
        
        # 短期タスクも保存 (SHORT_TERM)
        for st in short_tasks:
            st_goal = GoalHistory(
                goal_type="SHORT_TERM",
                goal_text_ja=st.get("ja", ""),
                goal_text_en=st.get("en", ""),
                status="ACTIVE"
            )
            db.add(st_goal)
            
        db.commit()
        logger.info(f"Generated new goals | 目標を生成しました: {goal_ja[:20]}...")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to generate goals | 目標生成に失敗: {e}")

def get_active_goals(db: Session) -> dict:
    daily = db.query(GoalHistory).filter_by(goal_type="DAILY", status="ACTIVE").first()
    shorts = db.query(GoalHistory).filter_by(goal_type="SHORT_TERM", status="ACTIVE").all()
    
    return {
        "daily": daily,
        "short_tasks": shorts
    }
