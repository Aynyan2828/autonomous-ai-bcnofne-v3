import os
import asyncio
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import SessionLocal
from shared.models import SystemState, SystemLog

# --- Dummy Usage Provider Adapter ---
class OpenAIApiUsageAdapter:
    """実際のOpenAI等の課金APIが接続されるまでのダミーアダプタ"""
    def __init__(self):
        self.dummy_cost: float = 0.0

    def get_todays_cost_jpy(self) -> float:
        # 実際にはここに OpenAI usage endpoint 等を叩くロジックを入れる
        # MVPでは、呼び出すたびに少しずつコストが蓄積するモックとする
        self.dummy_cost += 15.0 # ダミーのコスト蓄積
        return self.dummy_cost

usage_adapter = OpenAIApiUsageAdapter()

# --- Config & Setup ---
app = FastAPI(title="shipOS Billing Guard")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def log_event(db: Session, level: str, message: str):
    log_entry = SystemLog(service_name="billing-guard", level=level, message=message)
    db.add(log_entry)
    db.commit()

def calculate_days_from_start(db: Session) -> int:
    """システムのインストール日からの日数を計算"""
    install_date_state = db.query(SystemState).filter_by(key="install_date").first()
    now_date = datetime.now(timezone.utc).date()
    
    if not install_date_state or not install_date_state.value:
        # 初回起動時: 今日の日付を保存
        new_state = SystemState(key="install_date", value=now_date.isoformat())
        db.add(new_state)
        db.commit()
        return 0 # 0日目
    else:
        try:
            install_date = datetime.fromisoformat(install_date_state.value).date()
            return (now_date - install_date).days
        except ValueError:
            return 0

def is_special_day(days: int) -> bool:
    """0, 6, 12, 18, 24, 30... の特別日判定"""
    return days % 6 == 0

def enforce_limits(db: Session):
    days_running = calculate_days_from_start(db)
    special_day = is_special_day(days_running)
    current_cost_jpy = usage_adapter.get_todays_cost_jpy()

    # 閾値設定
    if special_day:
        warning_threshold, alert_threshold, stop_threshold = 500, 900, 1000
    else:
        warning_threshold, alert_threshold, stop_threshold = 200, 200, 300 # 通常日は200で注意、300で即停止

    alert_state = db.query(SystemState).filter_by(key="billing_alert_level").first()
    current_alert_level = alert_state.value if alert_state else "NORMAL"

    new_alert_level = "NORMAL"
    should_stop_ai = False
    log_msg = None

    if current_cost_jpy >= stop_threshold:
        new_alert_level = "STOP"
        should_stop_ai = True
        log_msg = f"【緊急停止】本日の課金額（{current_cost_jpy}円）が上限（{stop_threshold}円）に達しました。AIシステムを安全停止します。"
    elif current_cost_jpy >= alert_threshold and current_alert_level != "ALERT":
        new_alert_level = "ALERT"
        log_msg = f"【警告】本日の課金額が{alert_threshold}円を超過しました。（現在: {current_cost_jpy}円）"
    elif current_cost_jpy >= warning_threshold and current_alert_level not in ["ALERT", "WARNING", "STOP"]:
        new_alert_level = "WARNING"
        log_msg = f"【注意】本日の課金額が{warning_threshold}円を超過しました。（現在: {current_cost_jpy}円）"

    if new_alert_level != "NORMAL" and current_alert_level != new_alert_level:
        # アラートレベル更新
        if alert_state:
            alert_state.value = new_alert_level
        else:
            db.add(SystemState(key="billing_alert_level", value=new_alert_level))
        
        # ログ記録
        if log_msg:
            log_event(db, "CRITICAL" if should_stop_ai else "WARN", log_msg)
            # Todo: Notify core via LINE here or from core's internal watchdog
        
        # AI停止措置 (core等他サービスにストップを伝えるフラグをDBにセット)
        if should_stop_ai:
            ai_status = db.query(SystemState).filter_by(key="ai_status").first()
            if not ai_status:
                db.add(SystemState(key="ai_status", value="STOPPED"))
            else:
                ai_status.value = "STOPPED"
            
            stop_reason = db.query(SystemState).filter_by(key="ai_stop_reason").first()
            if not stop_reason:
                db.add(SystemState(key="ai_stop_reason", value="課金上限到達のため"))
            else:
                stop_reason.value = "課金上限到達のため"

        db.commit()

# --- Background Task ---
async def billing_monitor_task():
    """定期的に課金状況を監視するバックグラウンドタスク"""
    while True:
        try:
            db = SessionLocal()
            # Wait for table creation
            try:
                db.execute("SELECT 1 FROM system_state LIMIT 1")
            except Exception:
                db.close()
                await asyncio.sleep(5)
                continue
                
            enforce_limits(db)
            db.close()
        except Exception as e:
            print(f"Error in billing monitor: {e}")
        await asyncio.sleep(600)  # 10分おきにチェック

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    task = asyncio.create_task(billing_monitor_task())
    yield
    # Shutdown
    task.cancel()

app.router.lifespan_context = lifespan

# --- API Endpoints ---
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "billing-guard"}

@app.get("/status")
def get_billing_status(db: Session = Depends(get_db)):
    days_running = calculate_days_from_start(db)
    special_day = is_special_day(days_running)
    current_cost_jpy = usage_adapter.get_todays_cost_jpy()
    
    alert_state = db.query(SystemState).filter_by(key="billing_alert_level").first()
    alert_level = alert_state.value if alert_state else "NORMAL"
    
    return {
        "status": "ok",
        "current_cost_jpy": current_cost_jpy,
        "days_running": days_running,
        "is_special_day": special_day,
        "alert_level": alert_level
    }

@app.post("/check_high_cost_operation")
def check_operation(estimated_cost_jpy: float, db: Session = Depends(get_db)):
    """高コスト処理前に許可が可能か確認するエンドポイント"""
    days_running = calculate_days_from_start(db)
    special_day = is_special_day(days_running)
    current_cost_jpy = usage_adapter.get_todays_cost_jpy()
    
    stop_threshold = 1000 if special_day else 300
    if current_cost_jpy + estimated_cost_jpy >= stop_threshold:
        return {"allowed": False, "reason": "課金上限に到達するか超過の恐れがあります。マスターの許可が必要です。"}
    return {"allowed": True}
