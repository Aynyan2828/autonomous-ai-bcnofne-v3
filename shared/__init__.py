from sqlalchemy import text, inspect
from .database import engine, longterm_engine, get_db, SessionLocal
from .models import Base, SystemState, DiaryEntry, Memory, SystemLog, ShipMode, LogLevel, SelfModelParam, InternalStateHistory, GoalHistory, EvolutionLog

def migrate_db(target_engine):
    """欠落しているカラムを自動で追加する簡易マイグレーション処操"""
    inspector = inspect(target_engine)
    if "memories" in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns("memories")]
        if "layer" not in columns:
            with target_engine.connect() as conn:
                conn.execute(text("ALTER TABLE memories ADD COLUMN layer VARCHAR DEFAULT 'EPISODIC'"))
                conn.commit()
                print(f"[INIT] Added missing column 'layer' to 'memories' table.")

    if "improvement_proposals" in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns("improvement_proposals")]
        missing_columns = []
        
        if "plan_json" not in columns: missing_columns.append("ALTER TABLE improvement_proposals ADD COLUMN plan_json TEXT")
        if "files_affected" not in columns: missing_columns.append("ALTER TABLE improvement_proposals ADD COLUMN files_affected TEXT")
        if "diff_content" not in columns: missing_columns.append("ALTER TABLE improvement_proposals ADD COLUMN diff_content TEXT")
        if "test_results" not in columns: missing_columns.append("ALTER TABLE improvement_proposals ADD COLUMN test_results TEXT")
        if "failure_stage" not in columns: missing_columns.append("ALTER TABLE improvement_proposals ADD COLUMN failure_stage VARCHAR")
        if "failure_count" not in columns: missing_columns.append("ALTER TABLE improvement_proposals ADD COLUMN failure_count INTEGER DEFAULT 0")
        if "last_error_summary" not in columns: missing_columns.append("ALTER TABLE improvement_proposals ADD COLUMN last_error_summary TEXT")
        if "attempt_history" not in columns: missing_columns.append("ALTER TABLE improvement_proposals ADD COLUMN attempt_history TEXT")
        if "target_selection_reason" not in columns: missing_columns.append("ALTER TABLE improvement_proposals ADD COLUMN target_selection_reason TEXT")
        if "confidence" not in columns: missing_columns.append("ALTER TABLE improvement_proposals ADD COLUMN confidence FLOAT DEFAULT 0.0")
        if "evidence_summary" not in columns: missing_columns.append("ALTER TABLE improvement_proposals ADD COLUMN evidence_summary TEXT")
        
        if missing_columns:
            with target_engine.connect() as conn:
                for stmt in missing_columns:
                    conn.execute(text(stmt))
                conn.commit()
                print(f"[INIT] Added {len(missing_columns)} missing columns to 'improvement_proposals' table.")

# 初期化用関数 (core などから起動時に呼び出す)
def init_db():
    # 1. 基礎構成の作成
    # SSD (短期記憶)
    Base.metadata.create_all(bind=engine)
    # HDD (長期記憶)
    Base.metadata.create_all(bind=longterm_engine)
    
    # 2. 自動マイグレーション実行処操
    migrate_db(engine)
    migrate_db(longterm_engine)
