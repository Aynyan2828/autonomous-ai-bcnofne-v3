import os
import sys
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import SessionLocal
from shared.models import SystemLog, DiaryEntry

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

    class Config:
        orm_mode = True

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "diary-service"}

@app.post("/diary/generate", response_model=DiaryResponse)
def generate_diary(date_str: str = None, db: Session = Depends(get_db)):
    """
    指定された日付のシステムログや記憶を元に航海日誌（要約）を生成する。
    date_str が未指定の場合は今日の日付を使用。
    """
    if not date_str:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 既に日誌が存在するか確認
    existing_entry = db.query(DiaryEntry).filter(DiaryEntry.date_str == date_str).first()
    if existing_entry:
        return existing_entry

    # 対象日のログを取得 (本来は日付でフィルタする)
    logs = db.query(SystemLog).order_by(SystemLog.created_at.desc()).limit(20).all()
    
    # === 本来はここでLLM(OpenAI等)にログを投げて要約を生成する ===
    # MVP用のダミーロジック
    error_count = sum(1 for log in logs if log.level in ["ERROR", "CRITICAL"])
    if error_count > 0:
        summary_text_dummy = f"今日（{date_str}）はエラーが {error_count} 件あったばい。少し波が荒かったかもしれんね。"
    else:
        summary_text_dummy = f"今日（{date_str}）は異常なし！順調な航海やったよ。\nマスター、お疲れ様！"
    
    # 簡易なログリストを添付
    log_summaries = "\n".join([f"- {l.service_name}: {l.message}" for l in logs[:5]])
    full_summary = f"{summary_text_dummy}\n\n【主な出来事】\n{log_summaries}"

    new_entry = DiaryEntry(date_str=date_str, summary=full_summary)
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)

    return new_entry

@app.get("/diary/{date_str}", response_model=DiaryResponse)
def get_diary(date_str: str, db: Session = Depends(get_db)):
    entry = db.query(DiaryEntry).filter(DiaryEntry.date_str == date_str).first()
    if not entry:
        raise HTTPException(status_code=404, detail="その日の日誌はまだ書かれとらんよ。")
    return entry
