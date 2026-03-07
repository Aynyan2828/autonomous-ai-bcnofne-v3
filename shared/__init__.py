# Shared package setup
from .database import Base, engine, get_db, SessionLocal
from .models import SystemState, DiaryEntry, Memory, SystemLog, ShipMode, LogLevel

# 初期化用関数 (core などから起動時に呼び出す)
def init_db():
    Base.metadata.create_all(bind=engine)
