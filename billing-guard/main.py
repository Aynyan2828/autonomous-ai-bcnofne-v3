import os
import asyncio
import httpx
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import SessionLocal
from shared.models import SystemState, SystemLog
from shared.logger import ShipLogger

logger = ShipLogger("billing-guard")

# --- OpenAI Usage Tracker ---
class OpenAIUsageTracker:
    """
    OpenAI API の利用状況を追跡する。
    実際の Usage API が利用できない場合は、core/dev-agent の呼び出しをカウントして概算する。
    """
    def __init__(self):
        self._estimated_cost_jpy = 0.0
        self._request_count = 0
        self._last_reset_date = datetime.now(timezone.utc).date()

    def _reset_if_new_day(self):
        today = datetime.now(timezone.utc).date()
        if today != self._last_reset_date:
            self._estimated_cost_jpy = 0.0
            self._request_count = 0
            self._last_reset_date = today

    def record_request(self, model: str = "gpt-4o-mini", input_tokens: int = 500, output_tokens: int = 500):
        """API呼び出し1回分のコストを記録する"""
        self._reset_if_new_day()
        # GPT-4o-mini の料金 (2024年概算): input=$0.15/1M tokens, output=$0.60/1M tokens
        # GPT-4o: input=$2.50/1M tokens, output=$10.00/1M tokens
        cost_usd = 0.0
        if "4o-mini" in model:
            cost_usd = (input_tokens * 0.15 + output_tokens * 0.60) / 1_000_000
        elif "4o" in model:
            cost_usd = (input_tokens * 2.50 + output_tokens * 10.00) / 1_000_000
        else:
            cost_usd = (input_tokens * 0.50 + output_tokens * 1.50) / 1_000_000
        
        cost_jpy = cost_usd * 150  # 概算レート
        self._estimated_cost_jpy += cost_jpy
        self._request_count += 1

    def get_todays_cost_jpy(self) -> float:
        self._reset_if_new_day()
        return round(self._estimated_cost_jpy, 2)

    def get_request_count(self) -> int:
        self._reset_if_new_day()
        return self._request_count


usage_tracker = OpenAIUsageTracker()

# --- Config & Setup ---
app = FastAPI(title="shipOS Billing Guard")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def log_event(db: Session, level: str, message: str):
    if level == "INFO":
        logger.info(message)
    elif level == "WARN":
        logger.warn(message)
    elif level == "CRITICAL" or level == "ERROR":
        logger.critical(message)

def get_install_date(db: Session) -> str:
    install_date_state = db.query(SystemState).filter_by(key="install_date").first()
    now_date = datetime.now(timezone.utc).date()
    
    if not install_date_state or not install_date_state.value:
        new_state = SystemState(key="install_date", value=now_date.isoformat())
        db.add(new_state)
        db.commit()
        return now_date.isoformat()
    return install_date_state.value

def calculate_days_from_start(install_date_str: str) -> int:
    try:
        install_date = datetime.fromisoformat(install_date_str).date()
        now_date = datetime.now(timezone.utc).date()
        return (now_date - install_date).days
    except ValueError:
        return 0

def is_special_day(days: int) -> bool:
    """0, 6, 12, 18, 24, 30... の特別日判定"""
    return days % 6 == 0

def enforce_limits(db: Session):
    """課金上限チェック"""
    install_date_str = get_install_date(db)
    days_running = calculate_days_from_start(install_date_str)
    special_day = is_special_day(days_running)
    current_cost_jpy = usage_tracker.get_todays_cost_jpy()

    # 閾値設定
    if special_day:
        warning_threshold, alert_threshold, stop_threshold = 500, 900, 1000
    else:
        warning_threshold, alert_threshold, stop_threshold = 200, 200, 300

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
        if alert_state:
            alert_state.value = new_alert_level
        else:
            db.add(SystemState(key="billing_alert_level", value=new_alert_level))
        
        if log_msg:
            log_event(db, "CRITICAL" if should_stop_ai else "WARN", log_msg)
        
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
    task = asyncio.create_task(billing_monitor_task())
    logger.info("Billing Guard started. Monitoring API costs.")
    yield
    task.cancel()

app.router.lifespan_context = lifespan

# --- API Endpoints ---
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "billing-guard"}

@app.get("/status")
def get_billing_status(db: Session = Depends(get_db)):
    install_date_str = get_install_date(db)
    days_running = calculate_days_from_start(install_date_str)
    special_day = is_special_day(days_running)
    current_cost_jpy = usage_tracker.get_todays_cost_jpy()
    request_count = usage_tracker.get_request_count()
    
    if special_day:
        warning_threshold, alert_threshold, stop_threshold = 500, 900, 1000
    else:
        warning_threshold, alert_threshold, stop_threshold = 200, 200, 300
    
    alert_state = db.query(SystemState).filter_by(key="billing_alert_level").first()
    alert_level = alert_state.value if alert_state else "NORMAL"
    
    return {
        "status": "ok",
        "current_cost_jpy": current_cost_jpy,
        "request_count": request_count,
        "days_running": days_running,
        "start_date": install_date_str,
        "is_special_day": special_day,
        "alert_level": alert_level,
        "warning_threshold": warning_threshold,
        "alert_threshold": alert_threshold,
        "stop_threshold": stop_threshold,
    }

@app.post("/record")
def record_usage(model: str = "gpt-4o-mini", input_tokens: int = 500, output_tokens: int = 500):
    """他サービスから呼ばれ、API使用量を記録する"""
    usage_tracker.record_request(model=model, input_tokens=input_tokens, output_tokens=output_tokens)
    return {"status": "recorded", "current_cost_jpy": usage_tracker.get_todays_cost_jpy()}

@app.post("/check_high_cost_operation")
def check_operation(estimated_cost_jpy: float, db: Session = Depends(get_db)):
    install_date_str = get_install_date(db)
    days_running = calculate_days_from_start(install_date_str)
    special_day = is_special_day(days_running)
    current_cost_jpy = usage_tracker.get_todays_cost_jpy()
    
    stop_threshold = 1000 if special_day else 300
    if current_cost_jpy + estimated_cost_jpy >= stop_threshold:
        return {"allowed": False, "reason": "課金上限に到達するか超過の恐れがあります。マスターの許可が必要です。"}
    return {"allowed": True}
