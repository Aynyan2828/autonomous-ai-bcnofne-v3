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
from shared.bilingual_formatter import format_bilingual

# データベース初期化
init_db()
from datetime import datetime, timezone, timedelta
from llm import get_llm_executor

app = FastAPI(title="shipOS Memory Service")
logger = ShipLogger("memory-service")

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

    model_config = {
        "from_attributes": True
    }

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

    model_config = {
        "from_attributes": True
    }

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "memory-service"}

@app.post("/memories/", response_model=MemoryResponse)
async def create_memory(memory: MemoryCreate, db: Session = Depends(get_db), ldb: Session = Depends(get_longterm_db)):
    """記憶を作成。多層メモリ対応。"""
    
    # 0. AI による重要度とレイヤーの再分類 (Optional)
    # 明示的に指定されていない場合や、自動分類が有効な場合に実施
    if memory.layer == MemoryLayer.EPISODIC.value and memory.importance == 1:
        try:
            executor = await get_llm_executor()
            res = await executor.execute_json(
                task_type="classification",
                variables={"input_text": f"Topic: {memory.topic}\nContent: {memory.content}"}
            )
            # ClassificationResult { primary_label, confident, reason }
            memory.layer = res.get("primary_label", memory.layer)
            # 信頼度に基づき重要度を調整 (簡易実装)
            memory.importance = int(res.get("confidence", 0.5) * 5) or 1
        except Exception as e:
            logger.warn(f"Failed to auto-classify memory: {e}")

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
    if memory.importance >= 4 or memory.layer in [MemoryLayer.REFLECTIVE.value, MemoryLayer.SEMANTIC.value, MemoryLayer.RELATIONAL.value]:
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

@app.get("/memories/recall", response_model=List[MemoryResponse])
async def recall_memories(query: str, limit: int = 5, db: Session = Depends(get_db), ldb: Session = Depends(get_longterm_db)):
    """
    クエリに関連する記憶を想起する。
    1. SSD から直近の関連メモリを検索
    2. HDD から重要度の高い関連メモリを検索 (将来的にセマンティック検索へ拡張)
    """
    # 簡易実装: キーワードマッチング
    ssd_mems = db.query(Memory).filter(
        (Memory.topic.contains(query)) | (Memory.content.contains(query))
    ).order_by(Memory.importance.desc(), Memory.created_at.desc()).limit(limit).all()
    
    if len(ssd_mems) < limit:
        hdd_limit = limit - len(ssd_mems)
        hdd_mems = ldb.query(Memory).filter(
            (Memory.topic.contains(query)) | (Memory.content.contains(query))
        ).order_by(Memory.importance.desc(), Memory.created_at.desc()).limit(hdd_limit).all()
        ssd_mems.extend(hdd_mems)
    
    return ssd_mems

@app.get("/memories/", response_model=List[MemoryResponse])
def get_memories(topic: Optional[str] = None, layer: Optional[str] = None, limit: int = 10, db: Session = Depends(get_db)):
    """SSD (短期記憶) から取得"""
    query = db.query(Memory)
    if topic:
        query = query.filter(Memory.topic == topic)
    if layer:
        query = query.filter(Memory.layer == layer)
    return query.order_by(Memory.created_at.desc()).limit(limit).all()

@app.get("/longterm-memories/", response_model=List[MemoryResponse])
def get_longterm_memories(topic: Optional[str] = None, layer: Optional[str] = None, limit: int = 20, ldb: Session = Depends(get_longterm_db)):
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
        priority_layers = [MemoryLayer.MISSION.value, MemoryLayer.REFLECTIVE.value, MemoryLayer.SEMANTIC.value, MemoryLayer.RELATIONAL.value]
        memories = db.query(Memory).filter(Memory.layer.in_(priority_layers)).order_by(Memory.importance.desc(), Memory.created_at.desc()).limit(10).all()
        
        # 通常の記憶も追加
        recent_memories = db.query(Memory).filter(Memory.layer.in_([MemoryLayer.EPISODIC.value, MemoryLayer.WORKING.value])).order_by(Memory.created_at.desc()).limit(15).all()
        memories.extend(recent_memories)

        if not memories:
            return {"summary": "特に記憶していることはなかよ。"}
        
        # 重複排除 (IDで一意にする)
        seen_ids = set()
        unique_mems = []
        for m in memories:
            if m.id not in seen_ids:
                unique_mems.append(m)
                seen_ids.add(m.id)

        summary_text = "現在の脳内コンテキストばい:\n" + "\n".join([f"- [{m.layer}/{m.topic}] {m.content}" for m in unique_mems])
        return {"summary": summary_text}
    except Exception as e:
        import traceback
        error_msg = f"Summary error: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@app.get("/lessons", response_model=List[MemoryResponse])
def get_lessons(limit: int = 10, db: Session = Depends(get_db)):
    """
    dev-agent などの自律改善向けに、過去の教訓（REFLECTIVE層）を抽出して返す。
    """
    try:
        lessons = db.query(Memory).filter(
            Memory.layer == MemoryLayer.REFLECTIVE.value
        ).order_by(Memory.created_at.desc()).limit(limit).all()
        return lessons
    except Exception as e:
        logger.error(f"Failed to fetch lessons: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/memories/reflect")
async def reflect_memories(db: Session = Depends(get_db)):
    """
    1日の終わりに動作し、直近の WORKING / EPISODIC な記憶を要約して
    REFLECTIVE な記憶として沈殿（保存）させる Job エンドポイント。
    """
    one_day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    target_layers = [MemoryLayer.WORKING.value, MemoryLayer.EPISODIC.value]
    recent_memories = db.query(Memory).filter(
        Memory.layer.in_(target_layers),
        Memory.created_at >= one_day_ago
    ).all()
    
    if not recent_memories:
        return {"status": "skipped", "message": "No recent memories to reflect on."}
        
    mem_texts = [f"- [{m.topic}] {m.content}" for m in recent_memories]
    mem_context = "\n".join(mem_texts)

    try:
        # テンプレート化されたプロンプト管理構成経由で要約を実行
        executor = await get_llm_executor()
        result = await executor.execute_summarization(
            text=mem_context
        )
        reflection_text = result.final_summary
        
        # REFLECTIVE メモリとして保存
        new_memory = Memory(
            topic="Daily Reflection",
            content=reflection_text,
            layer=MemoryLayer.REFLECTIVE.value,
            importance=4
        )
        db.add(new_memory)
        
        # 処理済みの古い WORKING メモリなどは削除
        db.query(Memory).filter(Memory.layer == MemoryLayer.WORKING.value, Memory.created_at >= one_day_ago).delete()
        
        db.commit()
        logger.info(format_bilingual("Memory reflection 完了ばい！", "Memory reflection completed!"))
        
        return {"status": "success", "reflection": reflection_text}
    except Exception as e:
        logger.error(f"Reflection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
def get_proposals(status: Optional[str] = None, limit: int = 10, db: Session = Depends(get_db)):
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
