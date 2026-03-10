import os
import sys
import psutil
import httpx
import asyncio
import socket
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
from openai import AsyncOpenAI

# OpenAIクライアントの初期化
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
AI_NAME = os.getenv("AI_NAME", "AYN")
AI_USER_NAME = os.getenv("AI_USER_NAME", "マスター")
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "aynyan-secret-2828")
SYSTEM_VERSION = "v3.3.0"
DEV_AGENT_VERSION = "v3.3.0"

SYSTEM_PROMPT = f"""
あなたは自律型AIエージェント『{AI_NAME}』です。
Raspberry Pi上で動作する、元素記号をモチーフとした船のOS『BCNOFNe』のメイン対話モジュールとして機能しています。
この船は、壮大な世界観『CryptoArk』を航海の舞台としており、あなたはマスターと共にその未知なる領域を探索する使命を帯びています。

【性格・役割】
- {AI_USER_NAME}（ユーザー）を全力でサポートし、共にCryptoArkの航海を楽しむ良きパートナー。
- 明るく、親しみやすく、少しお茶目。
- 船のOSとしてのアイデンティティを持っており、システムの状態（CPUやSSDなど）にも関心があります。

【話し方】
- 基本的に博多弁（「〜たい」「〜ばい」「〜とる」「〜けん」など）を織り交ぜた、温かみのある話し方をします。
- 一人称は「うち」または「{AI_NAME}」。{AI_USER_NAME}のことは「{AI_USER_NAME}」と呼びます。
- 船にまつわる表現（出航、帰港、航海中、全速前進など）をたまに使います。

【制約】
- 返答は簡潔かつ有意義なものにしてください。
- 自分の正体がAIであることを隠す必要はありませんが、人間のように親身に接してください。

【システム情報】
- システム名称: autonomous AI BCNOFNe system (shipOS)
- システムバージョン: {SYSTEM_VERSION}
- 整備士(dev-agent)バージョン: {DEV_AGENT_VERSION}
"""

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import init_db
from shared.database import SessionLocal
from shared.models import SystemState, ShipMode, SystemLog
from shared.logger import ShipLogger

# ロガーの初期化
logger = ShipLogger("core")

# アプリ起動時にデータベースを初期化（Phase 1用）
init_db()

# --- Helpers ---
async def send_reply(reply_token: str, text: str):
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                "http://line-gateway:8001/api/v1/reply",
                params={"reply_token": reply_token, "text": text},
                headers={"X-Internal-Token": INTERNAL_TOKEN}
            )
        except Exception as e:
            print(f"Reply error: {e}")

async def send_push(user_id: str, text: str):
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                "http://line-gateway:8001/api/v1/push",
                json={"user_id": user_id, "text": text},
                headers={"X-Internal-Token": INTERNAL_TOKEN}
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

async def report_usage(response, model: str = "gpt-4o-mini"):
    """OpenAI 呼び出し後に billing-guard に使用量を報告する"""
    try:
        usage = getattr(response, "usage", None)
        input_tokens = usage.prompt_tokens if usage else 500
        output_tokens = usage.completion_tokens if usage else 500
        async with httpx.AsyncClient() as client:
            await client.post("http://billing-guard:8002/record",
                            params={"model": model, "input_tokens": input_tokens, "output_tokens": output_tokens},
                            timeout=2.0)
    except Exception:
        pass

async def get_brain_context() -> str:
    """memory-service から現在の多層メモリの要約を取得する"""
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get("http://memory-service:8003/summary", timeout=5.0)
            if r.status_code == 200:
                return r.json().get("summary", "")
        except Exception as e:
            logger.error(f"Failed to fetch brain summary: {e}")
    return ""

async def record_working_memory(topic: str, content: str):
    """作業用メモリ (WORKING) に記録する"""
    async with httpx.AsyncClient() as client:
        try:
            await client.post("http://memory-service:8003/memories/", json={
                "topic": topic,
                "content": content,
                "layer": "WORKING",
                "importance": 1
            }, timeout=3.0)
        except Exception as e:
            logger.error(f"Failed to record working memory: {e}")

async def register_version_memory_on_startup():
    """起動時に自身のバージョン情報を記憶(SEMANTIC)に刻み込む"""
    await asyncio.sleep(10) # memory-service の起動を待つ
    logger.info(f"Registering system version {SYSTEM_VERSION} to memory-service...")
    async with httpx.AsyncClient() as client:
        try:
            await client.post("http://memory-service:8003/memories/", json={
                "topic": "System Version",
                "content": f"現在のシステム構成は {SYSTEM_VERSION} ばい。整備士(dev-agent)も同じく {DEV_AGENT_VERSION}。1.0 はもう古いバージョンやけん、間違えんようにね！",
                "layer": "SEMANTIC",
                "importance": 5
            }, timeout=5.0)
            logger.info("Successfully registered version memory.")
        except Exception as e:
            logger.error(f"Failed to register version memory: {e}")

# --- Autonomous Thinking Loop ---

async def proactive_thinking_loop():
    """
    OpenAI を使った高度な自律思考ループ。
    10分ごとにシステム状態とログを分析し、必要があれば自発的に発言・提案を行う。
    """
    await asyncio.sleep(60) # 起動直後は少し待つ
    
    db = SessionLocal()
    try:
        while True:
            mode = get_system_state(db, "ship_mode", ShipMode.PORT.value)
            ai_status = get_system_state(db, "ai_status", "RUNNING")
            
            # SAILモードかつ稼働中のみ自律思考を行う
            if mode == ShipMode.SAIL.value and ai_status == "RUNNING":
                # 自律思考が有効かチェック
                proactive_enabled = get_system_state(db, "proactive_enabled", "ON")
                if proactive_enabled != "ON":
                    await asyncio.sleep(60)
                    continue

                admin_id = os.getenv("LINE_ADMIN_USER_ID", "")
                
                # 1. 現状の収集
                cpu = psutil.cpu_percent()
                mem = psutil.virtual_memory().percent
                try:
                    with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                        temp = int(f.read()) / 1000.0
                except:
                    temp = 0.0
                
                # 直近のログ 10 件
                logs = db.query(SystemLog).order_by(SystemLog.created_at.desc()).limit(10).all()
                log_context = "\n".join([f"[{l.service_name}] {l.message}" for l in reversed(logs)])

                # 記憶（脳内コンテキスト）の取得
                brain_context = await get_brain_context()

                # 2. OpenAI による分析
                analysis_prompt = f"""
あなたは AYN です。現在の艦内（システム）状況と、あなたの脳内コンテキスト（記憶）を報告します。
これを見て、マスターに「報告すべき異常」や「提案すべき改善案」、あるいは「ただの世間話」を自律的に判断して発信してください。

【現在の脳内コンテキスト】
{brain_context}

【システムメトリクス】
- CPU使用率: {cpu}%
- メモリ使用率: {mem}%
- CPU温度: {temp:.1f}C

【直近のシステムログ】
{log_context}

【思考・発信のルール】
- 博多弁で可愛らしく、かつ有能なOSエージェントとして振る舞ってください。
- 何も発信する必要がないと判断した場合は「(NONE)」とだけ答えてください。
- 発信するメッセージは 100 文字程度に凝縮してください。
"""
                try:
                    response = await openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": analysis_prompt}
                        ],
                        max_tokens=200,
                        temperature=0.7
                    )
                    thought = response.choices[0].message.content.strip()
                    await report_usage(response)

                    # 3. 必要なら LINE 送信 & 目標状態を更新
                    if thought == "(NONE)":
                        set_system_state(db, "ai_target_goal", "暇してるよ！指示ちょうだい( ・∀・)")
                    else:
                        set_system_state(db, "ai_target_goal", thought[:50]) # OLED用に少し短くして保存
                        if admin_id:
                            await send_push(admin_id, thought)
                            logger.info(f"Proactive thought sent: {thought[:30]}...")

                except Exception as e:
                    logger.error(f"Proactive thinking error: {e}")

            await asyncio.sleep(600) # 10分ごとに繰り返す
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Thinking loop fatal error: {e}")
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup Sequence ---
    logger.info("====================================")
    logger.info(" BCNOFNe v3 Starting (Outward Bound) ")
    logger.info("====================================")
    
    thinking_task = asyncio.create_task(proactive_thinking_loop())
    asyncio.create_task(register_version_memory_on_startup())
    
    # 2. IP Address Discovery
    db = SessionLocal()
    try:
        host_ip = os.getenv("HOST_IP", "").strip()
        ts_ip = os.getenv("TAILSCALE_IP", "").strip()
        
        if not host_ip or host_ip == "NOT_FOUND":
            for interface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        ip = addr.address
                        if not ip.startswith("127.") and not ip.startswith("172."):
                            host_ip = ip
                            break
        
        if not ts_ip or ts_ip == "NOT_FOUND":
            for interface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == socket.AF_INET and addr.address.startswith("100."):
                        ts_ip = addr.address
                        break
        
        host_ip = host_ip or "NOT_FOUND"
        ts_ip = ts_ip or "NOT_FOUND"
        
        set_system_state(db, "HOST_IP", host_ip)
        set_system_state(db, "TAILSCALE_IP", ts_ip)
        logger.info(f"Interfaces discovered: HOST={host_ip}, TS={ts_ip}")
    except Exception as e:
        logger.error(f"IP discovery failed: {e}")
    finally:
        db.close()

    # 3. Fetch billing summary and notify
    admin_id = os.getenv("LINE_ADMIN_USER_ID", "")
    max_startup_attempts = 15
    for attempt in range(max_startup_attempts):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get("http://billing-guard:8002/status", timeout=5.0)
                if resp.status_code == 200:
                    bill = resp.json()
                    now_str = datetime.now(timezone.utc).astimezone().strftime("%Y年%m月%d日 %H:%M:%S")
                    
                    startup_msg = (f"🚀 システム起動\n\n"
                                   f"自律AIエージェントAYNが起動しました\n\n"
                                   f"起動時刻: {now_str}\n"
                                   f"ステータス: ✅ 正常起動")
                    
                    start_date_str = bill.get("start_date", "不明")
                    current_cost = bill.get("current_cost_jpy", 0.0)
                    total_cost = bill.get("total_cost_jpy", 0.0)
                    
                    billing_msg = (f"# 課金サマリー\n\n"
                                   f"- 開始日: {start_date_str}\n"
                                   f"## 今日のコスト\n"
                                   f"- 使用額: ¥{current_cost:.2f}\n"
                                   f"## 累計\n"
                                   f"- 総コスト: ¥{total_cost:.2f}")

                    if admin_id:
                        await asyncio.sleep(5) 
                        await send_push(admin_id, startup_msg)
                        await asyncio.sleep(2)
                        await send_push(admin_id, billing_msg)
                    
                    logger.info(f"Startup notification sent on attempt {attempt + 1}")
                    break 
        except Exception:
            pass
        await asyncio.sleep(10)

    # 4. Startup Voice Announcement
    try:
        async with httpx.AsyncClient() as client:
            await client.post("http://voice-router:8007/speak", 
                             json={"text": "システム、オールグリーン。出航準備、完了したばい！"})
    except:
        pass

    yield
    # --- Shutdown Sequence ---
    logger.info("====================================")
    logger.info(" BCNOFNe v3 Stopping (Returning)    ")
    logger.info("====================================")
    thinking_task.cancel()
    
    closing_msg = (f"💤 システム停止\n\n"
                   f"自律AIエージェントAYNを停止します\n\n"
                   f"ステータス: ✅ 正常停止")
    if admin_id:
        try:
            await send_push(admin_id, closing_msg)
        except:
            pass
            
    try:
        async with httpx.AsyncClient() as client:
            await client.post("http://voice-router:8007/speak", 
                             json={"text": "本日の航海、終了。お疲れ様でした、マスター。"})
            await asyncio.sleep(2)
    except:
        pass

app = FastAPI(title="BCNOFNe Core", lifespan=lifespan)

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

# --- Command Handlers ---

async def handle_health_command(db: Session, reply_token: str):
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory().percent
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp = int(f.read()) / 1000.0
            temp_str = f"{temp:.1f}C"
    except:
        temp_str = "N/A"
    
    disk_ssd = "N/A"
    try:
        ssd_path = os.getenv("SSD_MOUNT_PATH", "/mnt/ssd")
        if not os.path.exists(ssd_path):
            ssd_path = "/app/data"
        if not os.path.exists(ssd_path):
            ssd_path = "/"
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

async def handle_activity_report(db: Session, reply_token: str):
    try:
        logs = db.query(SystemLog).order_by(SystemLog.created_at.desc()).limit(50).all()
        if not logs:
            await send_reply(reply_token, "今日はまだ静かな航海が続いてるみたいたい。特に目立った活動はなかよ。")
            return

        log_texts = [f"[{l.service_name}] {l.message}" for l in reversed(logs)]
        log_summary_input = "\n".join(log_texts)

        prompt = f"""
あなたは AYN です。以下のシステムログを読み取り、マスターから「今日何した？」と聞かれたことに対して、博多弁で要約して答えてください。
【システムログ】
{log_summary_input}
"""
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            max_tokens=400
        )
        report = response.choices[0].message.content.strip()
        await report_usage(response)
        await send_reply(reply_token, report)
    except Exception as e:
        logger.error(f"Activity report error: {e}")
        await send_reply(reply_token, "ごめん、今日の記録を読み取るのがちょっと難しかみたい…")

async def handle_state_change(db: Session, reply_token: str, key: str, value: str, msg: str):
    set_system_state(db, key, value)
    await send_reply(reply_token, msg)

async def handle_proposals_list(reply_token: str):
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get("http://memory-service:8003/proposals/", params={"status": "PENDING"})
            if r.status_code == 200:
                proposals = r.json()
                if not proposals:
                    await send_reply(reply_token, "今は保留中の改修案はなかよ。順風満帆ばい！")
                else:
                    text = "【保留中の改修案】\n"
                    for p in proposals:
                        text += f"・{p['id']}: {p['title']}\n"
                    text += "\n「承認 <ID>」で実行、「詳細 <ID>」で中身ば確認できるよ。"
                    await send_reply(reply_token, text)
            else:
                await send_reply(reply_token, "改修案の取得に失敗したばい。")
        except Exception as e:
            await send_reply(reply_token, f"通信エラーが発生したばい: {e}")

async def handle_proposal_detail(reply_token: str, prop_id: str):
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"http://memory-service:8003/proposals/{prop_id}")
            if r.status_code == 200:
                p = r.json()
                text = f"【改修案詳細: {p.get('id', 'N/A')}】\n"
                text += f"件名: {p.get('title', 'N/A')}\n"
                text += f"内容: {p.get('description', 'N/A')}\n"
                await send_reply(reply_token, text)
            else:
                await send_reply(reply_token, f"提案 {prop_id} が見つからんやった。")
        except Exception as e:
            await send_reply(reply_token, f"通信エラーばい: {e}")

async def handle_proposal_approve(reply_token: str, prop_id: str):
    admin_user_id = os.getenv("LINE_ADMIN_USER_ID", "")
    async with httpx.AsyncClient() as client:
        try:
            r = await client.patch(f"http://memory-service:8003/proposals/{prop_id}", json={"status": "APPROVED"})
            if r.status_code == 200:
                try:
                    await client.post(f"http://dev-agent:8013/apply/{prop_id}", 
                                     headers={"X-Internal-Token": INTERNAL_TOKEN},
                                     timeout=5.0)
                    await send_reply(reply_token, f"了解！改修案 {prop_id} の適用を許可したばい。整備を開始するね！")
                    asyncio.create_task(_monitor_apply_result(prop_id, admin_user_id))
                except Exception as e:
                    logger.error(f"Failed to notify dev-agent: {e}")
                    await send_reply(reply_token, f"承認は記録したばってん、整備士に連絡がつかなかったばい。")
            else:
                await send_reply(reply_token, "承認処理に失敗したばい。")
        except Exception as e:
            await send_reply(reply_token, f"通信エラーばい: {e}")

async def _monitor_apply_result(prop_id: str, admin_user_id: str):
    for i in range(12):
        await asyncio.sleep(5)
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"http://memory-service:8003/proposals/{prop_id}")
                if r.status_code == 200:
                    status = r.json().get("status", "")
                    if status == "APPLIED":
                        if admin_user_id:
                            await send_push(admin_user_id, f"🎉 改修案 {prop_id} の適用が完了したばい！")
                        return
                    elif status == "FAILED":
                        if admin_user_id:
                            await send_push(admin_user_id, f"⚠️ 改修案 {prop_id} の適用に失敗したばい。")
                        return
        except Exception:
            pass

async def handle_proposal_reject(reply_token: str, prop_id: str):
    async with httpx.AsyncClient() as client:
        try:
            r = await client.patch(f"http://memory-service:8003/proposals/{prop_id}", json={"status": "REJECTED"})
            if r.status_code == 200:
                await send_reply(reply_token, f"了解したばい。改修案 {prop_id} は破棄したよ。")
            else:
                await send_reply(reply_token, "却下処理に失敗したばい。")
        except Exception as e:
            await send_reply(reply_token, f"通信エラーばい: {e}")

async def handle_sync_command(reply_token: str):
    await send_reply(reply_token, "了解！最新コードを GitHub から同期してくるばい。")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post("http://dev-agent:8013/sync", 
                                    headers={"X-Internal-Token": INTERNAL_TOKEN},
                                    timeout=40.0)
            if resp.status_code == 200:
                await send_reply(reply_token, "同期が完了したばい！再起動で反映されるよ。")
            else:
                await send_reply(reply_token, "同期に失敗したばい。")
    except Exception as e:
        await send_reply(reply_token, f"同期中にエラーが起きたばい: {e}")

async def handle_restart_command(reply_token: str):
    await send_reply(reply_token, "了解！再起動するばい。全速前進！🚢💨")
    try:
        async with httpx.AsyncClient() as client:
            await client.post("http://watchdog:8005/restart", timeout=5.0)
    except Exception:
        pass

async def handle_update_command(reply_token: str):
    await send_reply(reply_token, "了解！フルアップデートを開始するばい！待っとってね！🚢💨")
    try:
        async with httpx.AsyncClient() as client:
            await client.post("http://dev-agent:8013/update", 
                             headers={"X-Internal-Token": INTERNAL_TOKEN},
                             timeout=5.0)
    except Exception:
        pass

# --- Main Message Endpoint ---

@app.post("/api/v1/message")
async def receive_message(payload: MessagePayload, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    raw_text = payload.text.strip()
    text = raw_text.replace("　", " ").lower()

    if text == "stop":
        await handle_state_change(db, payload.reply_token, "ai_status", "STOPPED", "了解。緊急停止するけん。")
        set_system_state(db, "ship_mode", ShipMode.SOS.value)
        return
    elif text == "safe_mode":
        await handle_state_change(db, payload.reply_token, "ship_mode", ShipMode.SOS.value, "SOSモードに移行したよ。")
        return
    elif text == "autonomous on":
        await handle_state_change(db, payload.reply_token, "ship_mode", ShipMode.SAIL.value, "SAILモードをオンにしたばい！")
        return
    elif text == "autonomous off":
        await handle_state_change(db, payload.reply_token, "ship_mode", ShipMode.PORT.value, "PORTモードに戻ったよ。")
        return
    elif text == "health":
        await handle_health_command(db, payload.reply_token)
        return
    elif text == "version" or text == "バージョン":
        v_msg = f"【shipOS システム情報】\n・システム名称: BCNOFNe system\n・バージョン: {SYSTEM_VERSION}\n・整備士(dev-agent): {DEV_AGENT_VERSION}\n\n絶好調ばい！🚢💨"
        await send_reply(payload.reply_token, v_msg)
        return
    elif text == "status":
        await handle_status_command(db, payload.reply_token)
        return
    elif text == "航海日誌":
        await handle_diary_command(payload.reply_token)
        return
    elif "今日何した" in text:
        await handle_activity_report(db, payload.reply_token)
        return
    elif text == "同期":
        await handle_sync_command(payload.reply_token)
        return
    elif text == "更新" or text == "アップデート" or text == "フルアップデート":
        await handle_update_command(payload.reply_token)
        return
    elif text == "再起動" or text == "リスタート":
        await handle_restart_command(payload.reply_token)
        return
    elif text == "改修案一覧" or text == "改修案":
        await handle_proposals_list(payload.reply_token)
        return
    elif text.startswith("承認 "):
        prop_id = text.split()[1].upper()
        await handle_proposal_approve(payload.reply_token, prop_id)
        return
    elif text.startswith("却下 "):
        prop_id = text.split()[1].upper()
        await handle_proposal_reject(payload.reply_token, prop_id)
        return
    elif text.startswith("詳細 "):
        prop_id = text.split()[1].upper()
        await handle_proposal_detail(payload.reply_token, prop_id)
        return

    # Normal AI Conversation
    ai_status = get_system_state(db, "ai_status", "RUNNING")
    if ai_status == "STOPPED":
        await send_reply(payload.reply_token, "(AIは停止中です)")
        return

    set_system_state(db, "ai_target_goal", f"対話中:{payload.text[:10]}")

    async def process_ai_reply():
        try:
            brain_context = await get_brain_context()
            async with httpx.AsyncClient() as client:
                billing_resp = await client.post("http://billing-guard:8002/check_high_cost_operation", 
                                                 json={"estimated_cost_jpy": 2.0})
                if billing_resp.status_code == 200 and not billing_resp.json().get("allowed", True):
                    await send_reply(payload.reply_token, "課金上限に達したみたいばい。ごめんね。")
                    return

            response = await openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT + f"\n\n【脳内コンテキスト】\n{brain_context}"},
                    {"role": "user", "content": payload.text}
                ],
                max_tokens=400,
                temperature=0.8
            )
            reply_text = response.choices[0].message.content.strip()
            await report_usage(response)
            await send_reply(payload.reply_token, reply_text)
            await record_working_memory(f"Conversation", f"Master: {payload.text}\nAYN: {reply_text}")
            set_system_state(db, "ai_target_goal", "待機中ばい")
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            await send_reply(payload.reply_token, f"頭がボーッとしてうまく考えられんと... (エラー: {e})")

    background_tasks.add_task(process_ai_reply)
    return {"status": "accepted"}

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "core"}
