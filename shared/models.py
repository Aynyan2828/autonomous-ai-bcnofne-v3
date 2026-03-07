from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, Enum
from datetime import datetime, timezone
import enum
from .database import Base

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
    """AIが保持する記憶 (プロンプト生成時に読み込む)"""
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String, index=True)
    content = Column(Text, nullable=False)
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
