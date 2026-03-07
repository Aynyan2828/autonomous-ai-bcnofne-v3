import os
import sys
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import SessionLocal
from shared.models import Memory

app = FastAPI(title="shipOS Memory Service")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class MemoryCreate(BaseModel):
    topic: str
    content: str
    importance: int = 1

class MemoryResponse(BaseModel):
    id: int
    topic: str
    content: str
    importance: int

    class Config:
        orm_mode = True

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "memory-service"}

@app.post("/memories/", response_model=MemoryResponse)
def create_memory(memory: MemoryCreate, db: Session = Depends(get_db)):
    db_memory = Memory(
        topic=memory.topic,
        content=memory.content,
        importance=memory.importance
    )
    db.add(db_memory)
    db.commit()
    db.refresh(db_memory)
    return db_memory

@app.get("/memories/", response_model=List[MemoryResponse])
def get_memories(topic: str = None, limit: int = 10, db: Session = Depends(get_db)):
    query = db.query(Memory)
    if topic:
        query = query.filter(Memory.topic == topic)
    return query.order_by(Memory.created_at.desc()).limit(limit).all()

@app.get("/summary")
def get_memory_summary(db: Session = Depends(get_db)):
    """現在保持している重要な記憶を適当に要約するエンドポイント（日本語対応）"""
    # 実際にはここに LLM (OpenAI) を使った要約ロジックを入れるか、core側で要約させる
    # MVPではDBから直接取得した最近のテキストを結合して返す
    memories = db.query(Memory).order_by(Memory.importance.desc(), Memory.created_at.desc()).limit(5).all()
    if not memories:
        return {"summary": "特に記憶していることはなかよ。"}
    
    summary_text = "最近の記憶ばい:\n" + "\n".join([f"- [{m.topic}] {m.content}" for m in memories])
    return {"summary": summary_text}
