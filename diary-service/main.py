import os
import sys
import httpx
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from openai import OpenAI

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import init_db
from shared.database import SessionLocal
from shared.models import SystemLog, DiaryEntry
from shared.bilingual_formatter import format_bilingual
from shared.public_exporter import export_to_public_markdown

# データベース初期化
init_db()

# Initialize OpenAI client (synchronous is fine here as it's just an API, but we could use async. For fastAPI standard def, sync works but blocks. We should probably use async or make the route async).
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
def generate_diary(date_str: str = None, db: Session = Depends(get_db)):
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

    prompt = f"""
あなたは AYN です。AI生命体としての1日の航海（システム稼働）を振り返り、航海日誌（Daily Voyage Log）を生成してください。
【本日のシステムログ】
{log_summary_input}

以下のフォーマットに従い、すべての項目を「日本語\\n英語的」なバイリンガル形式で出力してください。
博多弁を第一言語とします。

[Date] {date_str}

**1. System Events (主な出来事)**
(ここにシステムの稼働状況やエラーの有無、重要なシステムの動きを日英で)

**2. AI Reflection (AIの自己省察・感情)**
(ここにシステムメトリクスなどから感じたAI自身の感情や振り返りを日英で)

**3. Lessons Learned (本日の学び)**
(ここに今日経験したことからの学びを日英で)

**4. Next Focus (次の焦点)**
(明日以降に取り組むべき目標や課題を日英で)
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.7
        )
        full_summary = response.choices[0].message.content.strip()
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
