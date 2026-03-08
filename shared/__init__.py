from sqlalchemy import text, inspect
from .database import engine, longterm_engine, get_db, SessionLocal
from .models import Base, SystemState, DiaryEntry, Memory, SystemLog, ShipMode, LogLevel

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
