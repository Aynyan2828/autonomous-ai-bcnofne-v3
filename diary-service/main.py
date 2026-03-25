import os
import sys
import httpx
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from llm import get_llm_executor
from llm.schemas import FinalSummaryResult

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

class DiaryResponse(BaseModel):
    date_str: str
    summary: str

    model_config = {
        "from_attributes": True
    }

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "diary-service"}

@app.post("/diary/generate", response_model=DiaryResponse)
async def generate_diary(date_str: str = None, db: Session = Depends(get_db)):
    """
    指定された日付のシステムログや記憶を元に航海日誌（要約）を生成する。
    date_str が未指定の場合は今日の日付を使用。
    """
    if not date_str:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    existing_entry = db.query(DiaryEntry).filter(DiaryEntry.date_str == date_str).first()
    if existing_entry:
        return existing_entry

    logs = db.query(SystemLog).order_by(SystemLog.created_at.desc()).limit(100).all()
    log_texts = [f"[{l.service_name}] {l.level}: {l.message}" for l in reversed(logs)]
    log_summary_input = "\n".join(log_texts)

    try:
        # テンプレート化されたプロンプト管理構成経由で要約を実行
        executor = await get_llm_executor()
        result: FinalSummaryResult = await executor.execute_summarization(
            text=log_summary_input
        )
        full_summary = result.final_summary
    except Exception as e:
        full_summary = format_bilingual(
            f"日誌の生成中にエラーが起きたばい: {e}",
            f"Error occurred while generating voyage log: {e}"
        )

    new_entry = DiaryEntry(date_str=date_str, summary=full_summary)
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)

    # 公開用Markdownのエクスポート
    export_to_public_markdown("voyage_log", date_str, full_summary)

    return new_entry

@app.get("/diary/{date_str}", response_model=DiaryResponse)
def get_diary(date_str: str, db: Session = Depends(get_db)):
    entry = db.query(DiaryEntry).filter(DiaryEntry.date_str == date_str).first()
    if not entry:
        raise HTTPException(status_code=404, detail="その日の日誌はまだ書かれとらんよ。")
    return entry
