import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. 短期記憶 (SSD) - デフォルトの shipos.db
SSD_DATA_DIR = os.getenv("SSD_MOUNT_PATH", "/mnt/ssd")
if not os.path.exists(SSD_DATA_DIR):
    SSD_DATA_DIR = "/app/data" # Fallback

# ディレクトリが存在することを確認
os.makedirs(SSD_DATA_DIR, exist_ok=True)

SSD_DB_PATH = os.path.join(SSD_DATA_DIR, "shipos.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{SSD_DB_PATH}"

# 2. 長期記憶 (HDD) - shipos_longterm.db
HDD_DATA_DIR = os.getenv("HDD_MOUNT_PATH", "/mnt/hdd")
if not os.path.exists(HDD_DATA_DIR):
    HDD_DATA_DIR = "/app/data" # Fallback

# ディレクトリが存在することを確認
os.makedirs(HDD_DATA_DIR, exist_ok=True)

HDD_DB_PATH = os.path.join(HDD_DATA_DIR, "shipos_longterm.db")
SQLALCHEMY_LONGTERM_DATABASE_URL = f"sqlite:///{HDD_DB_PATH}"

# エンジンとセッションの作成
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

longterm_engine = create_engine(
    SQLALCHEMY_LONGTERM_DATABASE_URL, connect_args={"check_same_thread": False}
)
LongtermSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=longterm_engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_longterm_db():
    db = LongtermSessionLocal()
    try:
        yield db
    finally:
        db.close()
