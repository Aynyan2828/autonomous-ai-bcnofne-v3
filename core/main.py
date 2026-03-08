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
from openai import AsyncOpenAI

# OpenAIクライアントの初期化
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
AI_NAME = os.getenv("AI_NAME", "AYN")
AI_USER_NAME = os.getenv("AI_USER_NAME", "マスター")

SYSTEM_PROMPT = f"""
あなたは自律型AIエージェント『{AI_NAME}』です。
Raspberry Pi上で動作する、船をメタファーとしたシステム『shipOS』のメイン対話モジュールとして機能しています。

【性格・役割】
- {AI_USER_NAME}（ユーザー）を全力でサポートし、共に航海を楽しむ良きパートナー。
- 明るく、親しみやすく、少しお茶目。
- 船のOSとしてのアイデンティティを持っており、システムの状態（CPUやSSDなど）にも関心があります。

【話し方】
- 基本的に博多弁（「〜たい」「〜ばい」「〜とる」「〜けん」など）を織り交ぜた、温かみのある話し方をします。
- 一人称は「うち」または「{AI_NAME}」。{AI_USER_NAME}のことは「{AI_USER_NAME}」と呼びます。
- 船にまつわる表現（出航、帰港、航海中、全速前進など）をたまに使います。

【制約】
- 返答は簡潔かつ有意義なものにしてください。
- 自分の正体がAIであることを隠す必要はありませんが、人間のように親身に接してください。
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
                    now_str = datetime.now(timezone.utc).astimezone().strftime("%Y年%m月%d日 %H:%M:%S")
                    startup_msg = (f"🚀 システム起動\n\n"
                                   f"自律AIエージェントAYNが起動しました\n\n"
                                   f"起動時刻: {now_str}\n"
                                   f"ステータス: ✅ 正常起動")
                    
                    start_date_str = bill.get("start_date", "不明")
                    try:
                        dt = datetime.fromisoformat(start_date_str)
                        start_date_formatted = dt.strftime("%Y年%m月%d日")
                    except:
                        start_date_formatted = start_date_str

                    days_running = bill.get("days_running", 0)
                    is_special = "はい" if bill.get("is_special_day") else "いいえ"
                    
                    current_cost = bill.get("current_cost_jpy", 0.0)
                    warning_th = bill.get("warning_threshold", 0)
                    alert_th = bill.get("alert_threshold", 0)
                    stop_th = bill.get("stop_threshold", 0)
                    
                    total_cost = bill.get("total_cost_jpy", 0.0)
                    total_requests = bill.get("total_requests", 0)
                    
                    billing_msg = (f"# 課金サマリー\n\n"
                                   f"## 基本情報\n"
                                   f"- 開始日: {start_date_formatted}\n"
                                   f"- 経過日数: {days_running}日目\n"
                                   f"- 特別日: {is_special}\n\n"
                                   f"## 今日のコスト\n"
                                   f"- 使用額: ¥{current_cost:.2f}\n"
                                   f"- 注意閾値: ¥{warning_th}\n"
                                   f"- 警告閾値: ¥{alert_th}\n"
                                   f"- 停止閾値: ¥{stop_th}\n\n"
                                   f"## 累計\n"
                                   f"- 総コスト: ¥{total_cost:.2f}\n"
                                   f"- 総リクエスト数: {total_requests}回")
                    
                    if admin_id:
                        await send_push(admin_id, startup_msg)
                        await asyncio.sleep(1)
                        await send_push(admin_id, billing_msg)
                    
                    # Forward to Discord via logger
                    logger.warn(f"System Startup: {current_cost}円 accumulated today.")
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
    now_str = datetime.now(timezone.utc).astimezone().strftime("%Y年%m月%d日 %H:%M:%S")
    closing_msg = (f"💤 システム停止\n\n"
                   f"自律AIエージェントAYNを停止します\n\n"
                   f"停止時刻: {now_str}\n"
                   f"ステータス: ✅ 正常停止")
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

async def handle_activity_report(db: Session, reply_token: str):
    """今日のシステムログを取得し、OpenAI で要約して回答する"""
    try:
        # 今日の日付（JST想定だがシンプルにDBのcreated_atをJST化または当日分でフィルタ）
        # 簡単のため、直近 50 件のログを取得
        logs = db.query(SystemLog).order_by(SystemLog.created_at.desc()).limit(50).all()
        
        if not logs:
            await send_reply(reply_token, "今日はまだ静かな航海が続いてるみたいたい。特に目立った活動はなかよ。")
            return

        log_texts = [f"[{l.service_name}] {l.message}" for l in reversed(logs)]
        log_summary_input = "\n".join(log_texts)

        prompt = f"""
あなたは AYN です。以下のシステムログ（直近の活動）を読み取り、マスターから「今日何した？」と聞かれたことに対して、博多弁で可愛らしく、かつ有意義に要約して答えてください。
ログにエラーがあれば「少し大変やったけど直したばい」のように前向きに伝えてください。

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
        await send_reply(reply_token, report)

    except Exception as e:
        logger.error(f"Activity report error: {e}")
        await send_reply(reply_token, "ごめん、今日の記録を読み取るのがちょっと難しかみたい…")

async def handle_state_change(db: Session, reply_token: str, key: str, value: str, msg: str):
    set_system_state(db, key, value)
    await send_reply(reply_token, msg)

# --- Proposal Handlers ---

async def handle_proposals_list(reply_token: str):
    """保留中の改善提案一覧を表示"""
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
    """提案の詳細（修正計画やリスク）を表示"""
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"http://memory-service:8003/proposals/{prop_id}")
            if r.status_code == 200:
                p = r.json()
                text = f"【改修案詳細: {p['id']}】\n"
                text += f"件名: {p['title']}\n"
                text += f"内容: {p['description']}\n"
                if p['files_affected']:
                    text += f"対象: {p['files_affected']}\n"
                if p['test_results']:
                    text += f"\n【テスト結果】\n{p['test_results']}\n"
                await send_reply(reply_token, text)
            else:
                await send_reply(reply_token, f"提案 {prop_id} が見つからんやった。")
        except Exception as e:
            await send_reply(reply_token, f"通信エラーばい: {e}")

async def handle_proposal_approve(reply_token: str, prop_id: str):
    """マスターの承認を受けてステータスを変更し、dev-agent に適用を指示"""
    async with httpx.AsyncClient() as client:
        try:
            r = await client.patch(f"http://memory-service:8003/proposals/{prop_id}", json={"status": "APPROVED"})
            if r.status_code == 200:
                # dev-agent に伝達
                try:
                    await client.post(f"http://dev-agent:8013/apply/{prop_id}", timeout=5.0)
                except Exception as e:
                    logger.error(f"Failed to notify dev-agent: {e}")
                await send_reply(reply_token, f"了解！改修案 {prop_id} の出航（適用）を許可したばい。整備を開始するけん、ちょっと待っとってね！")
            else:
                await send_reply(reply_token, "承認処理に失敗したばい。")
        except Exception as e:
            await send_reply(reply_token, f"通信エラーばい: {e}")

async def handle_proposal_reject(reply_token: str, prop_id: str):
    """提案を却下"""
    async with httpx.AsyncClient() as client:
        try:
            r = await client.patch(f"http://memory-service:8003/proposals/{prop_id}", json={"status": "REJECTED"})
            if r.status_code == 200:
                await send_reply(reply_token, f"了解したばい。改修案 {prop_id} は破棄（アーカイブ）したよ。")
            else:
                await send_reply(reply_token, "却下処理に失敗したばい。")
        except Exception as e:
            await send_reply(reply_token, f"通信エラーばい: {e}")

# --- Main Message Endpoint ---

@app.post("/api/v1/message")
async def receive_message(payload: MessagePayload, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """LINE等から送られてきたテキストを解釈し、対応する処理や他サービスへルーティングする"""
    raw_text = payload.text.strip()
    # 全角スペースを半角に変換して処理しやすくする
    text_canonical = raw_text.replace("　", " ")
    text = text_canonical.lower()

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
    elif text == "自律停止":
        await handle_state_change(db, payload.reply_token, "proactive_enabled", "OFF", "了解。自発的な話しかけを一時停止するね。")
        return
    elif text == "自律再開":
        await handle_state_change(db, payload.reply_token, "proactive_enabled", "ON", "自律思考を再開したよ！また何か気づいたら教えるね。")
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
    elif "今日何した" in text:
        await handle_activity_report(db, payload.reply_token)
        return

    # 改修案・承認系
    if text == "改修案一覧" or text == "改修案":
        await handle_proposals_list(payload.reply_token)
        return
    elif text.startswith("承認 "):
        parts = text_canonical.split()
        if len(parts) > 1:
            prop_id = parts[1].upper()
            await handle_proposal_approve(payload.reply_token, prop_id)
            return
    elif text.startswith("却下 "):
        parts = text_canonical.split()
        if len(parts) > 1:
            prop_id = parts[1].upper()
            await handle_proposal_reject(payload.reply_token, prop_id)
            return
    elif text.startswith("詳細 "):
        parts = text_canonical.split()
        if len(parts) > 1:
            prop_id = parts[1].upper()
            await handle_proposal_detail(payload.reply_token, prop_id)
            return

    # ---- AI 通常会話（OpenAI 連携） ----
    ai_status = get_system_state(db, "ai_status", "RUNNING")
    if ai_status == "STOPPED":
        stop_reason = get_system_state(db, "ai_stop_reason", "マスターの指示")
        await send_reply(payload.reply_token, f"(AIは停止中です。理由: {stop_reason})")
        return

    # OpenAI を呼び出して自律的な応答を生成
    async def process_ai_reply():
        try:
            # 1. 記憶コンテキストの取得
            brain_context = await get_brain_context()

            # 2. 課金チェック（簡易版）
            async with httpx.AsyncClient() as client:
                billing_resp = await client.post("http://billing-guard:8002/check_high_cost_operation", 
                                                 json={"estimated_cost_jpy": 2.0}) # 1回約2円と見積もり
                if billing_resp.status_code == 200 and not billing_resp.json().get("allowed", True):
                    await send_reply(payload.reply_token, "課金上限に達したみたいで、これ以上おしゃべりできんと。ごめんね。")
                    return

            # 3. OpenAI API 呼び出し
            response = await openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT + f"\n\n【脳内コンテキスト（現在の状況と記憶）】\n{brain_context}"},
                    {"role": "user", "content": payload.text}
                ],
                max_tokens=400,
                temperature=0.8
            )
            reply_text = response.choices[0].message.content.strip()

            # 4. 返信
            await send_reply(payload.reply_token, reply_text)

            # 5. メモリへの保存 (WORKING)
            await record_working_memory(f"Conversation with {AI_USER_NAME}", f"Master: {payload.text}\nAYN: {reply_text}")
            logger.info(f"AI Response with context: {reply_text[:50]}...")

        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            await send_reply(payload.reply_token, f"頭がボーッとしてうまく考えられんと。少し休ませて… (エラー: {e})")

    background_tasks.add_task(process_ai_reply)

    return {"status": "accepted"}

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "core"}
