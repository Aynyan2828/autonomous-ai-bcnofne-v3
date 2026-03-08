import os
import sys
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import SessionLocal, LongtermSessionLocal, get_db, get_longterm_db
from shared.models import Memory, init_db # init_db を使って長期DBも初期化する
from shared.logger import ShipLogger

logger = ShipLogger("memory-service")

app = FastAPI(title="shipOS Memory Service")

# 起動時にデータベース（SSD/HDD両方）を準備
db_ssd = SessionLocal()
db_hdd = LongtermSessionLocal()
init_db() # 内部で Base.metadata.create_all が実行されるのを期待（shared/models.pyの構成依存）
db_ssd.close()
db_hdd.close()

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
def create_memory(memory: MemoryCreate, db: Session = Depends(get_db), ldb: Session = Depends(get_longterm_db)):
    """記憶を作成。重要度が高い(4以上)場合は HDD (長期) にも保存する。"""
    db_memory = Memory(
        topic=memory.topic,
        content=memory.content,
        importance=memory.importance
    )
    
    # 1. SSD (短期記憶) に保存
    db.add(db_memory)
    db.commit()
    db.refresh(db_memory)
    
    # 2. 重要度が高い場合は HDD (長期記憶) にも保存
    if memory.importance >= 4:
        try:
            long_memory = Memory(
                topic=memory.topic,
                content=memory.content,
                importance=memory.importance
            )
            ldb.add(long_memory)
            ldb.commit()
            logger.info(f"Long-term memory archived (HDD): {memory.topic}")
        except Exception as e:
            logger.error(f"Failed to save long-term memory: {e}")

    return db_memory

@app.get("/memories/", response_model=List[MemoryResponse])
def get_memories(topic: str = None, limit: int = 10, db: Session = Depends(get_db)):
    """SSD (短期記憶) から取得"""
    query = db.query(Memory)
    if topic:
        query = query.filter(Memory.topic == topic)
    return query.order_by(Memory.created_at.desc()).limit(limit).all()

@app.get("/longterm-memories/", response_model=List[MemoryResponse])
def get_longterm_memories(topic: str = None, limit: int = 20, ldb: Session = Depends(get_longterm_db)):
    """HDD (長期記憶) から取得"""
    query = ldb.query(Memory)
    if topic:
        query = query.filter(Memory.topic == topic)
    return query.order_by(Memory.created_at.desc()).limit(limit).all()

@app.get("/summary")
def get_memory_summary(db: Session = Depends(get_db)):
    """現在保持している重要な記憶を要約する。短期記憶を優先。"""
    memories = db.query(Memory).order_by(Memory.importance.desc(), Memory.created_at.desc()).limit(10).all()
    if not memories:
        return {"summary": "特に記憶していることはなかよ。"}
    
    summary_text = "最近の記憶ばい:\n" + "\n".join([f"- [{m.topic}] {m.content}" for m in memories])
    return {"summary": summary_text}
