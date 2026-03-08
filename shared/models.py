from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, Enum
from datetime import datetime, timezone
import enum
from sqlalchemy.orm import declarative_base

# Baseはモデル定義側で一元管理する
Base = declarative_base()

class ShipMode(str, enum.Enum):
    SAIL = "SAIL"       # autonomous
    PORT = "PORT"       # user_first
    DOCK = "DOCK"       # maintenance
    ANCHOR = "ANCHOR"   # power_save
    SOS = "SOS"         # safe mode

class LogLevel(str, enum.Enum):
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class MemoryLayer(str, enum.Enum):
    """人間の脳を模した多層メモリ層"""
    WORKING = "WORKING"      # 作業用一時メモリ (短命)
    EPISODIC = "EPISODIC"     # 出来事・履歴
    SEMANTIC = "SEMANTIC"     # 知識・仕様・恒常的情報
    PROCEDURAL = "PROCEDURAL" # 手順・スキル・ノウハウ
    REFLECTIVE = "REFLECTIVE" # 反省・学習・改善
    RELATIONAL = "RELATIONAL" # マスターとの関係性・好み
    MISSION = "MISSION"       # 中長期目標・保留タスク

class ProposalStatus(str, enum.Enum):
    """改善提案のステータス"""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"

class SystemState(Base):
    """システム全体の現在の状態を保持するKVS的なテーブル (1行またはキー単位で更新を想定)"""
    __tablename__ = "system_state"

    key = Column(String, primary_key=True, index=True)
    value = Column(String, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class DiaryEntry(Base):
    """航海日誌エントリ (要約済みテキストなど)"""
    __tablename__ = "diary_entries"

    id = Column(Integer, primary_key=True, index=True)
    date_str = Column(String, index=True) # YYYY-MM-DD
    summary = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Memory(Base):
    """AIが保持する記憶 (多層構造対応)"""
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String, index=True)
    content = Column(Text, nullable=False)
    layer = Column(String, default=MemoryLayer.EPISODIC.value, index=True) # メモリ層
    importance = Column(Integer, default=1) # 1-5
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class SystemLog(Base):
    """各サービスからのシステムイベントログ"""
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String, index=True)
    level = Column(String, index=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class AutoImprovementProposal(Base):
    """自律改善提案モデル (整備計画書)"""
    __tablename__ = "improvement_proposals"

    id = Column(String, primary_key=True, index=True) # "PROP-YYYYMMDD-XXXX"
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    plan_json = Column(Text, nullable=True)  # 修正計画詳細 (JSON)
    files_affected = Column(Text, nullable=True) # カンマ区切りファイルリスト
    diff_content = Column(Text, nullable=True) # 生成された差分
    test_results = Column(Text, nullable=True) # テスト結果要約
    status = Column(String, default=ProposalStatus.PENDING.value, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
