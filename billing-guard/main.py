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
from shared.logger import ShipLogger

logger = ShipLogger("billing-guard")

# --- Config & Setup ---
app = FastAPI(title="shipOS Billing Guard")

# Token pricing (USD per 1M tokens, 2024 rates)
PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "default": {"input": 0.50, "output": 1.50},
}
JPY_RATE = 150  # 概算レート

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _get_state(db: Session, key: str, default: str = "") -> str:
    s = db.query(SystemState).filter_by(key=key).first()
    return s.value if s else default

def _set_state(db: Session, key: str, value: str):
    s = db.query(SystemState).filter_by(key=key).first()
    if s:
        s.value = value
    else:
        db.add(SystemState(key=key, value=value))
    db.commit()

def _today_str() -> str:
    """JST ベースの今日の日付文字列"""
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).strftime("%Y-%m-%d")

def _get_todays_cost(db: Session) -> float:
    """DB から今日のコストを取得。日付が変わってたらリセット"""
    stored_date = _get_state(db, "billing_date", "")
    today = _today_str()
    if stored_date != today:
        # 日付変更 → リセット
        _set_state(db, "billing_date", today)
        _set_state(db, "billing_cost_jpy", "0.0")
        _set_state(db, "billing_requests", "0")
        _set_state(db, "billing_alert_level", "NORMAL")
        return 0.0
    return float(_get_state(db, "billing_cost_jpy", "0.0"))

def _get_request_count(db: Session) -> int:
    stored_date = _get_state(db, "billing_date", "")
    today = _today_str()
    if stored_date != today:
        return 0
    return int(_get_state(db, "billing_requests", "0"))

def log_event(db: Session, level: str, message: str):
    if level == "INFO":
        logger.info(message)
    elif level == "WARN":
        logger.warn(message)
    elif level == "CRITICAL" or level == "ERROR":
        logger.critical(message)

def get_install_date(db: Session) -> str:
    install_date_state = db.query(SystemState).filter_by(key="install_date").first()
    jst = timezone(timedelta(hours=9))
    now_date = datetime.now(jst).date()
    
    if not install_date_state or not install_date_state.value:
        new_state = SystemState(key="install_date", value=now_date.isoformat())
        db.add(new_state)
        db.commit()
        return now_date.isoformat()
    return install_date_state.value

def calculate_days_from_start(install_date_str: str) -> int:
    try:
        install_date = datetime.fromisoformat(install_date_str).date()
        jst = timezone(timedelta(hours=9))
        now_date = datetime.now(jst).date()
        return (now_date - install_date).days
    except ValueError:
        return 0

def is_special_day(days: int) -> bool:
    return days % 6 == 0

def enforce_limits(db: Session):
    """課金上限チェック"""
    install_date_str = get_install_date(db)
    days_running = calculate_days_from_start(install_date_str)
    special_day = is_special_day(days_running)
    current_cost_jpy = _get_todays_cost(db)

    if special_day:
        warning_threshold, alert_threshold, stop_threshold = 500, 900, 1000
    else:
        warning_threshold, alert_threshold, stop_threshold = 200, 200, 300

    current_alert_level = _get_state(db, "billing_alert_level", "NORMAL")

    new_alert_level = "NORMAL"
    should_stop_ai = False
    log_msg = None

    if current_cost_jpy >= stop_threshold:
        new_alert_level = "STOP"
        should_stop_ai = True
        log_msg = f"【緊急停止】本日の課金額（{current_cost_jpy:.1f}円）が上限（{stop_threshold}円）に達しました。"
    elif current_cost_jpy >= alert_threshold and current_alert_level != "ALERT":
        new_alert_level = "ALERT"
        log_msg = f"【警告】本日の課金額が{alert_threshold}円を超過（現在: {current_cost_jpy:.1f}円）"
    elif current_cost_jpy >= warning_threshold and current_alert_level not in ["ALERT", "WARNING", "STOP"]:
        new_alert_level = "WARNING"
        log_msg = f"【注意】本日の課金額が{warning_threshold}円を超過（現在: {current_cost_jpy:.1f}円）"

    if new_alert_level != "NORMAL" and current_alert_level != new_alert_level:
        _set_state(db, "billing_alert_level", new_alert_level)
        
        if log_msg:
            log_event(db, "CRITICAL" if should_stop_ai else "WARN", log_msg)
        
        if should_stop_ai:
            _set_state(db, "ai_status", "STOPPED")
            _set_state(db, "ai_stop_reason", "課金上限到達のため")

# --- Background Task ---
async def billing_monitor_task():
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
        await asyncio.sleep(600)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(billing_monitor_task())
    logger.info("Billing Guard started. Cost tracking is DB-persistent.")
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
    current_cost_jpy = _get_todays_cost(db)
    request_count = _get_request_count(db)
    
    if special_day:
        warning_threshold, alert_threshold, stop_threshold = 500, 900, 1000
    else:
        warning_threshold, alert_threshold, stop_threshold = 200, 200, 300
    
    alert_level = _get_state(db, "billing_alert_level", "NORMAL")
    
    return {
        "status": "ok",
        "current_cost_jpy": round(current_cost_jpy, 2),
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
def record_usage(model: str = "gpt-4o-mini", input_tokens: int = 500, output_tokens: int = 500, db: Session = Depends(get_db)):
    """他サービスから呼ばれ、API使用量をDBに永続記録する"""
    # 日付チェック＆リセット
    current_cost = _get_todays_cost(db)
    current_requests = _get_request_count(db)
    
    # コスト計算
    pricing = PRICING.get(model, PRICING["default"])
    # model名に部分一致で探す
    for key, rates in PRICING.items():
        if key != "default" and key in model:
            pricing = rates
            break
    
    cost_usd = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
    cost_jpy = cost_usd * JPY_RATE
    
    new_cost = current_cost + cost_jpy
    new_requests = current_requests + 1
    
    _set_state(db, "billing_cost_jpy", str(round(new_cost, 4)))
    _set_state(db, "billing_requests", str(new_requests))
    
    logger.info(f"Recorded: {model} in={input_tokens} out={output_tokens} +{cost_jpy:.4f}円 (total: {new_cost:.2f}円, #{new_requests})")
    
    return {
        "status": "recorded",
        "added_cost_jpy": round(cost_jpy, 4),
        "current_cost_jpy": round(new_cost, 2),
        "request_count": new_requests
    }

@app.post("/check_high_cost_operation")
def check_operation(estimated_cost_jpy: float, db: Session = Depends(get_db)):
    install_date_str = get_install_date(db)
    days_running = calculate_days_from_start(install_date_str)
    special_day = is_special_day(days_running)
    current_cost_jpy = _get_todays_cost(db)
    
    stop_threshold = 1000 if special_day else 300
    if current_cost_jpy + estimated_cost_jpy >= stop_threshold:
        return {"allowed": False, "reason": f"課金上限に到達の恐れ（現在:{current_cost_jpy:.1f}円 + 予定:{estimated_cost_jpy:.1f}円 >= {stop_threshold}円）"}
    return {"allowed": True}
