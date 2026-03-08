import os
import sys
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import SessionLocal, LongtermSessionLocal, get_db, get_longterm_db
from shared import init_db
from shared.models import Memory, AutoImprovementProposal, MemoryLayer, ProposalStatus
from shared.logger import ShipLogger
from datetime import datetime

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
    layer: str = MemoryLayer.EPISODIC.value
    importance: int = 1

class MemoryResponse(BaseModel):
    id: int
    topic: str
    content: str
    layer: str
    importance: int
    created_at: datetime

    class Config:
        orm_mode = True

class ProposalCreate(BaseModel):
    id: str
    title: str
    description: str
    plan_json: str | None = None
    files_affected: str | None = None
    diff_content: str | None = None
    test_results: str | None = None
    status: str | None = None

class ProposalUpdate(BaseModel):
    status: str | None = None
    test_results: str | None = None
    diff_content: str | None = None

class ProposalResponse(BaseModel):
    id: str
    title: str
    description: str
    files_affected: str | None = None
    plan_json: str | None = None
    diff_content: str | None = None
    test_results: str | None = None
    status: str
    created_at: datetime

    class Config:
        orm_mode = True

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "memory-service"}

@app.post("/memories/", response_model=MemoryResponse)
def create_memory(memory: MemoryCreate, db: Session = Depends(get_db), ldb: Session = Depends(get_longterm_db)):
    """記憶を作成。多層メモリ対応。"""
    db_memory = Memory(
        topic=memory.topic,
        content=memory.content,
        layer=memory.layer,
        importance=memory.importance
    )
    
    # 1. SSD (短期記憶) に保存
    db.add(db_memory)
    db.commit()
    db.refresh(db_memory)
    
    # 2. 重要度が高い、または特定の層は HDD (長期記憶) にも保存
    if memory.importance >= 4 or memory.layer in [MemoryLayer.REFLECTIVE.value, MemoryLayer.SEMANTIC.value]:
        try:
            long_memory = Memory(
                topic=memory.topic,
                content=memory.content,
                layer=memory.layer,
                importance=memory.importance
            )
            ldb.add(long_memory)
            ldb.commit()
            logger.info(f"Memory archived to HDD (Layer: {memory.layer}): {memory.topic}")
        except Exception as e:
            logger.error(f"Failed to save long-term memory: {e}")

    return db_memory

@app.get("/memories/", response_model=List[MemoryResponse])
def get_memories(topic: str = None, layer: str = None, limit: int = 10, db: Session = Depends(get_db)):
    """SSD (短期記憶) から取得"""
    query = db.query(Memory)
    if topic:
        query = query.filter(Memory.topic == topic)
    if layer:
        query = query.filter(Memory.layer == layer)
    return query.order_by(Memory.created_at.desc()).limit(limit).all()

@app.get("/longterm-memories/", response_model=List[MemoryResponse])
def get_longterm_memories(topic: str = None, layer: str = None, limit: int = 20, ldb: Session = Depends(get_longterm_db)):
    """HDD (長期記憶) から取得"""
    query = ldb.query(Memory)
    if topic:
        query = query.filter(Memory.topic == topic)
    if layer:
        query = query.filter(Memory.layer == layer)
    return query.order_by(Memory.created_at.desc()).limit(limit).all()

@app.get("/summary")
def get_memory_summary(db: Session = Depends(get_db)):
    """現在保持している重要な記憶を要約する。MISSION や REFLECTIVE を優先的に含める。"""
    try:
        logger.info("Memory summary requested via /summary")
        # 特定の層を優先して取得
        priority_layers = [MemoryLayer.MISSION.value, MemoryLayer.REFLECTIVE.value, MemoryLayer.SEMANTIC.value]
        memories = db.query(Memory).filter(Memory.layer.in_(priority_layers)).order_by(Memory.importance.desc(), Memory.created_at.desc()).limit(5).all()
        
        # 通常の記憶も追加
        recent_memories = db.query(Memory).filter(Memory.layer == MemoryLayer.EPISODIC.value).order_by(Memory.created_at.desc()).limit(5).all()
        memories.extend(recent_memories)

        if not memories:
            return {"summary": "特に記憶していることはなかよ。"}
        
        summary_text = "現在の脳内コンテキストばい:\n" + "\n".join([f"- [{m.layer}/{m.topic}] {m.content}" for m in memories])
        return {"summary": summary_text}
    except Exception as e:
        import traceback
        error_msg = f"Summary error: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

# --- Proposal Endpoints ---

@app.post("/proposals/", response_model=ProposalResponse)
def create_proposal(proposal: ProposalCreate, db: Session = Depends(get_db)):
    """改善提案（整備計画書）を保存"""
    db_proposal = AutoImprovementProposal(
        id=proposal.id,
        title=proposal.title,
        description=proposal.description,
        plan_json=proposal.plan_json,
        files_affected=proposal.files_affected,
        diff_content=proposal.diff_content,
        test_results=proposal.test_results,
        status=proposal.status or ProposalStatus.PENDING.value
    )
    db.add(db_proposal)
    db.commit()
    db.refresh(db_proposal)
    logger.info(f"New improvement proposal created: {proposal.id} (Status: {db_proposal.status})")
    return db_proposal

@app.get("/proposals/", response_model=List[ProposalResponse])
def get_proposals(status: str = None, limit: int = 10, db: Session = Depends(get_db)):
    """提案一覧を取得"""
    query = db.query(AutoImprovementProposal)
    if status:
        query = query.filter(AutoImprovementProposal.status == status)
    return query.order_by(AutoImprovementProposal.created_at.desc()).limit(limit).all()

@app.get("/proposals/{proposal_id}", response_model=ProposalResponse)
def get_proposal(proposal_id: str, db: Session = Depends(get_db)):
    """特定の提案詳細を取得"""
    proposal = db.query(AutoImprovementProposal).filter(AutoImprovementProposal.id == proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return proposal

@app.patch("/proposals/{proposal_id}", response_model=ProposalResponse)
def update_proposal(proposal_id: str, update: ProposalUpdate, db: Session = Depends(get_db)):
    """提案のステータスやテスト結果を更新"""
    db_proposal = db.query(AutoImprovementProposal).filter(AutoImprovementProposal.id == proposal_id).first()
    if not db_proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    if update.status:
        db_proposal.status = update.status
    if update.test_results:
        db_proposal.test_results = update.test_results
    if update.diff_content:
        db_proposal.diff_content = update.diff_content
        
    db.commit()
    db.refresh(db_proposal)
    logger.info(f"Proposal {proposal_id} updated: {update.status}")
    return db_proposal
