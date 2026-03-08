import os
import sys
import psutil
import httpx
import asyncio
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import init_db
from shared.database import SessionLocal
from shared.models import SystemState, ShipMode
from shared.logger import ShipLogger

# ロガーの初期化
logger = ShipLogger("core")

# アプリ起動時にデータベースを初期化（Phase 1用）
init_db()

app = FastAPI(title="shipOS Core")

class MessagePayload(BaseModel):
    text: str
    user_id: str
    reply_token: str
    source: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Helpers ---
async def send_reply(reply_token: str, text: str):
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                "http://line-gateway:8001/api/v1/reply",
                params={"reply_token": reply_token, "text": text}
            )
        except Exception as e:
            print(f"Reply error: {e}")

async def send_push(user_id: str, text: str):
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                "http://line-gateway:8001/api/v1/push",
                json={"user_id": user_id, "text": text}
            )
        except Exception as e:
            print(f"Push error: {e}")

def get_system_state(db: Session, key: str, default: str = "") -> str:
    state = db.query(SystemState).filter_by(key=key).first()
    return state.value if state else default

def set_system_state(db: Session, key: str, value: str):
    state = db.query(SystemState).filter_by(key=key).first()
    if state:
        state.value = value
    else:
        db.add(SystemState(key=key, value=value))
    db.commit()

# --- Autonomous Thinking Loop ---

async def proactive_thinking_loop():
    """
    Autonomous AI thinking loop (proactive mode).
    Periodically checks if the AI should say something or ask for permission.
    """
    # 起動直後の安定待ち
    await asyncio.sleep(10)
    
    db = SessionLocal()
    try:
        while True:
            # Check ship mode
            mode = get_system_state(db, "ship_mode", ShipMode.PORT.value)
            ai_status = get_system_state(db, "ai_status", "RUNNING")
            
            if mode == ShipMode.SAIL.value and ai_status == "RUNNING":
                # Get current task for context
                cur_task = get_system_state(db, "ai_target_goal", "System Monitoring")
                admin_id = os.getenv("LINE_ADMIN_USER_ID", "")

                # 1. Check for high CPU temp
                try:
                    with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                        cpu_temp = int(f.read()) / 1000.0
                        if cpu_temp > 70.0:
                            msg = f"マスター、機関温度が {cpu_temp:.1f}C まで上がっとうよ！自律判断で冷却ファンを最強にしてもよか？（返信で許可してね）"
                            if admin_id:
                                await send_push(admin_id, msg)
                except:
                    pass
                
                # 2. Simulated Proactive Question (Randomly or based on time)
                # In production, this would be an LLM-generated reflection on recent data
                import random
                if random.random() < 0.3: # 30% chance each loop
                    questions = [
                        f"現在「{cur_task}」中やけど、特に異常はなかよ。このまま進めてよか？",
                        "マスター、次の航海計画（タスク）について相談したかことがあっとやけど、今よか？",
                        "ログを分析した結果、バックアップを今のうちに取っといたほうがよかっちゃないかな？って思ったばい。許可してくれん？",
                        "記録領域（SSD）に少し空きが増えたけん、整理整頓はバッチリばい！"
                    ]
                    if admin_id:
                        await send_push(admin_id, random.choice(questions))
                
                # Update OLED track
                set_system_state(db, "ai_target_goal", cur_task)
                
            await asyncio.sleep(600)  # 10分ごとに思考
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"Thinking loop error: {e}")
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup Sequence ---
    logger.info("====================================")
    logger.info(" shipOS v3 Starting (Outward Bound) ")
    logger.info("====================================")
    
    # 1. Start thinking loop
    thinking_task = asyncio.create_task(proactive_thinking_loop())
    
    # 2. Fetch billing summary and notify
    admin_id = os.getenv("LINE_ADMIN_USER_ID", "")
    for attempt in range(5):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get("http://billing-guard:8002/status", timeout=5.0)
                if resp.status_code == 200:
                    bill = resp.json()
                    msg = (f"【出航報告】shipOS 起動完了ばい！\n"
                           f"本日累計: {bill['current_cost_jpy']}円\n"
                           f"稼海日数: {bill['days_running']}日目\n"
                           f"アラート: {bill['alert_level']}\n"
                           f"全システム、オールグリーン。さあ、行きましょう！")
                    if admin_id:
                        await send_push(admin_id, msg)
                    # Forward to Discord via logger
                    logger.warn(f"System Startup: {bill['current_cost_jpy']}円 accumulated today.")
                    break # Success
        except Exception as e:
            logger.info(f"Startup billing check attempt {attempt + 1}/5 failed: {e}")
            if attempt < 4:
                await asyncio.sleep(2.0)
            else:
                logger.error("Startup billing check failed after 5 attempts.")

    # 3. Startup Voice Announcement
    try:
        async with httpx.AsyncClient() as client:
            await client.post("http://voice-router:8007/speak", 
                             json={"text": "システム、オールグリーン。出航準備、完了したばい！"})
    except:
        pass

    yield

    # --- Shutdown Sequence ---
    logger.info("====================================")
    logger.info(" shipOS v3 Stopping (Returning)    ")
    logger.info("====================================")
    
    # 1. Stop thinking loop
    thinking_task.cancel()
    
    # 2. Final notification
    closing_msg = "【帰港報告】本日の航海を終了します。システムを停止し、待機モードに入ります。お疲れ様でした！"
    if admin_id:
        try:
            await send_push(admin_id, closing_msg)
        except:
            pass
    logger.warn("System Shutdown Initiated.")

    # 3. Shutdown Voice
    try:
        async with httpx.AsyncClient() as client:
            await client.post("http://voice-router:8007/speak", 
                             json={"text": "本日の航海、終了。お疲れ様でした、マスター。"})
            await asyncio.sleep(2) # 再生待ち
    except:
        pass

app.router.lifespan_context = lifespan

# --- Command Handlers ---

async def handle_health_command(db: Session, reply_token: str):
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory().percent
    try:
        # Raspberry Pi temperature
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp = int(f.read()) / 1000.0
            temp_str = f"{temp:.1f}C"
    except:
        temp_str = "N/A"
    
    disk_ssd = "N/A"
    try:
        ssd_path = os.getenv("SSD_MOUNT_PATH", "/mnt/ssd")
        if not os.path.exists(ssd_path):
            ssd_path = "/app/data" # Fallback to standard volume mount
        if not os.path.exists(ssd_path):
            ssd_path = "/" # Fallback to root
        ssd_usage = psutil.disk_usage(ssd_path).percent
        disk_ssd = f"{ssd_usage}%"
    except:
        pass
        
    ai_status = get_system_state(db, "ai_status", "RUNNING")
    billing_alert = get_system_state(db, "billing_alert_level", "NORMAL")
    mode = get_system_state(db, "ship_mode", ShipMode.PORT.value)

    res = (f"【System Health】\n"
           f"CPU: {cpu}%\n"
           f"Mem: {mem}%\n"
           f"Temp: {temp_str}\n"
           f"SSD: {disk_ssd}\n"
           f"AI Status: {ai_status}\n"
           f"Billing: {billing_alert}\n"
           f"Mode: {mode}")
    await send_reply(reply_token, res)

async def handle_status_command(db: Session, reply_token: str):
    states = db.query(SystemState).all()
    lines = [f"{s.key}: {s.value}" for s in states]
    res = "【Current System State】\n" + "\n".join(lines)
    if not lines:
        res = "状態データはまだなにもなかよ。"
    await send_reply(reply_token, res)

async def handle_diary_command(reply_token: str):
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post("http://diary-service:8004/diary/generate")
            if r.status_code == 200:
                data = r.json()
                await send_reply(reply_token, data["summary"])
            else:
                await send_reply(reply_token, "日誌の生成に失敗したばい。")
        except Exception as e:
            await send_reply(reply_token, f"日誌サービスと通信できんやった: {e}")

async def handle_state_change(db: Session, reply_token: str, key: str, value: str, msg: str):
    set_system_state(db, key, value)
    await send_reply(reply_token, msg)

# --- Main Message Endpoint ---

@app.post("/api/v1/message")
async def receive_message(payload: MessagePayload, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """LINE等から送られてきたテキストを解釈し、対応する処理や他サービスへルーティングする"""
    text = payload.text.strip().lower()

    # 安全系コマンド（最優先）
    if text == "stop":
        await handle_state_change(db, payload.reply_token, "ai_status", "STOPPED", "了解。緊急停止するけん。")
        set_system_state(db, "ship_mode", ShipMode.SOS.value)
        return
    elif text == "safe_mode":
        await handle_state_change(db, payload.reply_token, "ship_mode", ShipMode.SOS.value, "SOSモード(Safe Mode)に移行したよ。")
        return

    # モード切り替え系
    if text == "autonomous on":
        await handle_state_change(db, payload.reply_token, "ship_mode", ShipMode.SAIL.value, "SAILモード(自律運転)をオンにしたばい！")
        return
    elif text == "autonomous off":
        await handle_state_change(db, payload.reply_token, "ship_mode", ShipMode.PORT.value, "PORTモード(待機)に戻ったよ。")
        return
    elif text.startswith("voice mode"):
        parts = text.split()
        if len(parts) > 2:
            v_mode = parts[2].upper()
            if v_mode in ["NURSE", "OAI", "HYB"]:
                await handle_state_change(db, payload.reply_token, "voice_mode", v_mode, f"音声モードを {v_mode} に変更したよ。")
                return
        await send_reply(payload.reply_token, "voice mode は NURSE, OAI, HYB のどれかを指定してね。")
        return

    # 情報・確認系コマンド
    if text == "health":
        await handle_health_command(db, payload.reply_token)
        return
    elif text == "status":
        await handle_status_command(db, payload.reply_token)
        return
    elif text == "航海日誌":
        await handle_diary_command(payload.reply_token)
        return
    elif text == "今日何した？":
        await send_reply(payload.reply_token, "今日は少しファイル整理して、あとはずっとマスターのこと見守っとったよ！（※ダミー回答）")
        return

    # ---- AI 通常会話（OpenAI等へのプロキシ） ----
    ai_status = get_system_state(db, "ai_status", "RUNNING")
    if ai_status == "STOPPED":
        stop_reason = get_system_state(db, "ai_stop_reason", "マスターの指示")
        await send_reply(payload.reply_token, f"(AIは停止中です。理由: {stop_reason})")
        return

    # MVP: 会話スタブ。本来はここで課金チェックを行い、安全ならOpenAIを呼ぶ。
    # 話題に応じて memory-service に適宜保存させる
    background_tasks.add_task(send_reply, payload.reply_token, f"「{payload.text}」やね。了解たい！(MVP処理済)")

    return {"status": "accepted"}

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "core"}
