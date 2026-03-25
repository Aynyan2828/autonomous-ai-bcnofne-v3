import logging
import os
import sys
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from llm import get_llm_executor
from llm.schemas import FinalSummaryResult

logger = logging.getLogger("diary-service")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import init_db
from shared.database import SessionLocal
from shared.models import SystemLog, DiaryEntry
from shared.bilingual_formatter import format_bilingual
from shared.public_exporter import export_to_public_markdown

# データベース初期化
init_db()

# LLM プロバイダーの初期化は呼び出し時に行う

app = FastAPI(title="shipOS Diary Service")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from typing import List, Optional
import json

class DiaryResponse(BaseModel):
    date_str: str
    summary: str
    proposed_goals: Optional[List[str]] = None

    model_config = {
        "from_attributes": True
    }

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "diary-service"}

@app.post("/diary/generate", response_model=DiaryResponse)
async def generate_diary(date_str: Optional[str] = None, db: Session = Depends(get_db)):
    """
    指定された日付のシステムログや記憶を元に航海日誌（要約）を生成し、
    次回の目標（proposed_goals）を提案する。
    """
    from shared.models import Memory
    
    if not date_str:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    existing_entry = db.query(DiaryEntry).filter(DiaryEntry.date_str == date_str).first()
    if existing_entry:
        if isinstance(existing_entry.proposed_goals, str):
            try:
                existing_entry.proposed_goals = json.loads(existing_entry.proposed_goals)
            except:
                existing_entry.proposed_goals = []
        return existing_entry

    # 1. ログを取得
    logs = db.query(SystemLog).order_by(SystemLog.created_at.desc()).limit(50).all()
    log_texts = [f"[{l.service_name}] {l.message}" for l in reversed(logs)]
    
    # 2. 記憶 (Memory) を取得
    memories = db.query(Memory).order_by(Memory.importance.desc(), Memory.created_at.desc()).limit(20).all()
    mem_texts = [f"[{m.layer}/{m.topic}] {m.content}" for m in memories]
    
    combined_input = "### SYSTEM LOGS\n" + "\n".join(log_texts) + "\n\n### RECENT MEMORIES\n" + "\n".join(mem_texts)

    full_summary = ""
    proposed_goals = []

    try:
        executor = await get_llm_executor()
        # 日誌本体の生成
        result = await executor.execute_summarization(text=combined_input)
        full_summary = result.final_summary
        
        # 次のアクション（目標）の提案
        goal_res = await executor.execute_json(
            task_type="goal",
            variables={"context": full_summary}
        )
        # goal_res は GoalResult { daily_goal_ja, daily_goal_en, short_tasks }
        if goal_res:
            proposed_goals = [goal_res.get("daily_goal_ja", "")]
            # 短期タスクも追加
            tasks = goal_res.get("short_tasks", [])
            for t in tasks:
                if isinstance(t, dict):
                    proposed_goals.append(t.get("task", ""))
                else:
                    proposed_goals.append(str(t))

    except Exception as e:
        logger.error(f"Diary generation error: {e}")
        full_summary = f"日誌生成中にエラーが発生したばい... {e}"
        proposed_goals = ["システムの安定性を確認する"]

    new_entry = DiaryEntry(
        date_str=date_str, 
        summary=full_summary,
        proposed_goals=json.dumps(proposed_goals, ensure_ascii=False)
    )
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)

    # 公開用エクスポート (summaryのみ)
    export_to_public_markdown("voyage_log", date_str, full_summary)

    # レスポンス用にパース
    new_entry.proposed_goals = proposed_goals
    return new_entry

@app.get("/diary/{date_str}", response_model=DiaryResponse)
def get_diary(date_str: str, db: Session = Depends(get_db)):
    entry = db.query(DiaryEntry).filter(DiaryEntry.date_str == date_str).first()
    if not entry:
        raise HTTPException(status_code=404, detail="その日の日誌はまだ書かれとらんよ。")
    return entry
