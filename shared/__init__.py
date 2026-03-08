from .database import engine, longterm_engine, get_db, SessionLocal
from .models import Base, SystemState, DiaryEntry, Memory, SystemLog, ShipMode, LogLevel

# 初期化用関数 (core などから起動時に呼び出す)
def init_db():
    # SSD (短期記憶)
    Base.metadata.create_all(bind=engine)
    # HDD (長期記憶)
    Base.metadata.create_all(bind=longterm_engine)
