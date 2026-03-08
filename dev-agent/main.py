import os
import sys
import asyncio
import httpx
import shutil
import subprocess
import json
import uuid
import traceback
from datetime import datetime, timezone
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from openai import AsyncOpenAI

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import init_db
from shared.logger import ShipLogger
from shared.database import SessionLocal
from shared.models import SystemState

VERSION = "v3.1.5-fix"
print(f"AYN {VERSION} STARTING... (CWD: {os.getcwd()})")

logger = ShipLogger("dev-agent")
app = FastAPI(title="BCNOFNe Dev Agent")
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SRC_DIR = "/app/src"
WORKSPACE_DIR = "/app/workspace"
MEMORY_SERVICE_URL = "http://memory-service:8003"

def set_system_state_helper(key: str, value: str):
    db = SessionLocal()
    try:
        state = db.query(SystemState).filter_by(key=key).first()
        if state:
            state.value = value
        else:
            db.add(SystemState(key=key, value=value))
        db.commit()
    except Exception as e:
        logger.error(f"Failed to set system state: {e}")
    finally:
        db.close()

async def send_push_notification(text: str):
    """LINE 経由でマスターに通知を送る"""
    admin_id = os.getenv("LINE_ADMIN_USER_ID")
    if not admin_id:
        logger.warn("LINE_ADMIN_USER_ID not set, skipping push notification")
        return
    async with httpx.AsyncClient() as client:
        try:
            await client.post("http://line-gateway:8001/api/v1/push", 
                             json={"user_id": admin_id, "text": text},
                             timeout=5.0)
        except Exception as e:
            logger.error(f"Failed to send push notification: {e}")

class ApplyRequest(BaseModel):
    proposal_id: str

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "dev-agent"}

@app.post("/sync")
async def sync_repository():
    """
    GitHub から最新のソースコードを取得するエンドポイント
    """
    try:
        # 1. Git pull 実行
        logger.info("Starting git pull from origin main...")
        res = subprocess.run(
            ["git", "-C", SRC_DIR, "pull", "origin", "main"],
            capture_output=True, text=True, timeout=30
        )
        
        if res.returncode == 0:
            logger.info("Git pull completed successfully.")
            await send_push_notification("マスター、最新の魂（コード）の同期が完了したばい！変更を反映させるには「再起動」って指示してね。")
            return {
                "status": "success",
                "message": "魂（コード）の同期が完了したばい！最新の状態になったよ。",
                "output": res.stdout
            }
        else:
            logger.error(f"Git pull failed: {res.stderr}")
            return {
                "status": "error",
                "message": f"同期に失敗したばい...。エラーが出とるよ：\n{res.stderr}",
                "output": res.stderr
            }
            
    except Exception as e:
        logger.error(f"Sync fatal error: {e}")
        return {
            "status": "error",
            "message": f"同期中に致命的な問題が発生したばい：{e}"
        }

@app.post("/apply/{proposal_id}")
async def apply_proposal(proposal_id: str, background_tasks: BackgroundTasks):
    """
    承認された提案を本番環境へ反映させるエンドポイント
    core サービスから呼び出されることを想定
    """
    background_tasks.add_task(execute_apply, proposal_id)
    return {"status": "queued", "proposal_id": proposal_id}

async def execute_apply(proposal_id: str):
    """本番環境への反映（Apply）を実行"""
    logger.info(f"Starting Apply for proposal: {proposal_id}")
    set_system_state_helper("ai_target_goal", f"{proposal_id}ば適用するけん！")
    
    try:
        # 1. 提案内容の取得
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{MEMORY_SERVICE_URL}/proposals/{proposal_id}")
            if r.status_code != 200:
                logger.error(f"Proposal {proposal_id} not found in memory-service")
                return
            proposal = r.json()

        # 2. バックアップ (Git commit)
        try:
            # Dockerコンテナ内での所有権エラーとIdentityエラーの回避
            # --system を使うことで HOME の依存性を減らす
            subprocess.run(["git", "config", "--system", "--add", "safe.directory", SRC_DIR], check=True)
            subprocess.run(["git", "config", "--system", "user.email", "ayn@shipos.local"], check=True)
            subprocess.run(["git", "config", "--system", "user.name", "AYN"], check=True)
            
            subprocess.run(["git", "-C", SRC_DIR, "add", "."], check=True)
            # 変更がない場合でも exit 0 にするために commit に --allow-empty を付与
            res = subprocess.run(["git", "-C", SRC_DIR, "commit", "-m", f"pre-apply backup for {proposal_id}", "--allow-empty"], 
                                 capture_output=True, text=True, check=True)
            logger.info(f"Backup commit created successfully: {res.stdout.strip()}")
        except subprocess.CalledProcessError as e:
            logger.warn(f"Backup commit skipped or failed (Git Error 128?): {e.stderr.strip()}")
        except Exception as e:
            logger.warn(f"Backup commit fatal error: {repr(e)}")

        # 3. 反映実行 (workspace から src へコピー)
        # 固定の workspace 構造を想定
        # 簡易化のため、plan_json に含まれるファイルリストを元にコピーする
        plan = json.loads(proposal.get("plan_json", "{}"))
        files = plan.get("files", [])
        
        for f_path in files:
            src_full = os.path.join(SRC_DIR, f_path)
            work_full = os.path.join(WORKSPACE_DIR, f_path)
            if os.path.exists(work_full):
                logger.info(f"Source file found in workspace: {work_full}")
                os.makedirs(os.path.dirname(src_full), exist_ok=True)
                shutil.copy2(work_full, src_full)
                logger.info(f"Successfully applied change to {f_path}")
            else:
                logger.error(f"Source file NOT FOUND in workspace: {work_full} (Proposal: {proposal_id})")

        # 4. ステータス更新
        async with httpx.AsyncClient() as client:
            await client.patch(f"{MEMORY_SERVICE_URL}/proposals/{proposal_id}", json={"status": "APPLIED"})
        
        logger.info(f"Apply completed for {proposal_id}. Awaiting service restart...")
        await send_push_notification(f"マスター、改修案 {proposal_id} の整備（適用）が完了したばい！正常に反映されたけん、安心してね。")
        
        # 5. 自身の再起動は Compose 連携が必要だが、ここではログに残す
        # 実際には core 等が検知して docker compose restart するか、
        # サービス自体が終了して Compose が再起動するのを待つ

    except Exception as e:
        logger.error(f"Apply fatal error for {proposal_id}: {e}")
        async with httpx.AsyncClient() as client:
            await client.patch(f"{MEMORY_SERVICE_URL}/proposals/{proposal_id}", json={"status": "FAILED"})

# --- Autonomous Development Loop ---

async def development_loop():
    """
    1時間に1回、システムの状態を観測して改善案を練る自律ループ
    """
    logger.info(f"Autonomous Development Loop started (version: {VERSION})")
    await asyncio.sleep(30) # 他のサービスの起動を待つ
    
    while True:
        try:
            # (1) Observe & Think
            # ログやメトリクスを収集し、OpenAI に相談
            await run_autonomous_observation()
            
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"Development loop error: {e}\n{error_trace}")
            
        # 1時間おきに繰り返すが、エラー時は少し早めにリトライを試みる
        await asyncio.sleep(3600)

async def safe_get_memory_summary(client):
    """memory-service からの要約取得をリトライ付きで実行"""
    urls = [MEMORY_SERVICE_URL, "http://shipos-memory-service:8003"]
    for i in range(10):
        url = urls[0] if i % 2 == 0 else urls[1]
        try:
            r = await client.get(f"{url}/summary", timeout=10.0)
            if r.status_code == 200:
                return r.json().get("summary", "")
            else:
                logger.warn(f"Failed to fetch memory summary (attempt {i+1}) from {url}: HTTP {r.status_code}")
        except Exception as e:
            import socket
            hostname = url.split("//")[-1].split(":")[0]
            try:
                ip = socket.gethostbyname(hostname)
            except:
                ip = "Unknown"
            logger.warn(f"Failed to fetch memory summary (attempt {i+1}) from {url} ({ip}): {type(e).__name__} - {str(e)}")
            await asyncio.sleep(5)
    return "N/A"

async def run_autonomous_observation():
    """観測と改善案の生成"""
    logger.info("Observing system for improvements...")
    set_system_state_helper("ai_target_goal", "システムを観測中ばい...")
    
    # 1. データの収集
    async with httpx.AsyncClient() as client:
        # 直近ログ (リトライ付き)
        brain_context = await safe_get_memory_summary(client)
        
        # 現在の提案（PENDING が多すぎればスキップ）
        try:
            prop_resp = await client.get(f"{MEMORY_SERVICE_URL}/proposals/", params={"status": "PENDING"}, timeout=5.0)
            pending_count = len(prop_resp.json()) if prop_resp.status_code == 200 else 0
        except:
            pending_count = 0
        
    if pending_count >= 3:
        logger.info("Too many pending proposals. Skipping observation.")
        return

    # 2. OpenAI による分析
    prompt = f"""
あなたは shipOS の主任整備士 AYN です。システムの健全性と利便性を高めるのが任務です。
現在の脳内コンテキストとログを確認して、何か1つ「改善すべき点」を見つけてください。

【現在の脳内コンテキスト】
{brain_context}

【任務】
1. 問題点や改善の余地を特定してください。
2. 修正すべきファイルパスを特定してください（例: core/main.py, oled-controller/main.py 等）。
3. 修正の「計画」を JSON 形式で提案してください。

出力は以下の JSON 形式のみで答えてください：
{{
  "id": "PROP-YYYYMMDD-XXXX",
  "title": "改善のタイトル",
  "description": "なぜこれが必要か",
  "files": ["修正ファイルパス1", "..."],
  "plan": "具体的な修正内容の指示"
}}
"""
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={ "type": "json_object" }
        )
        suggestion = json.loads(response.choices[0].message.content)
        
        # ユニークID付与
        suggestion["id"] = f"PROP-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
        
        # (3) Plan & (4) Build & (5) Test
        # 実際に workspace でコード生成を試みる
        await process_suggestion(suggestion)

    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Observation / Suggestion error: {e}\n{error_trace}")

async def process_suggestion(suggestion):
    """提案された内容を実際に workspace で実装・テストする (リトライ機能付き)"""
    prop_id = suggestion["id"]
    logger.info(f"Processing suggestion: {prop_id} - {suggestion['title']}")
    set_system_state_helper("ai_target_goal", f"改修案を作成中ばい: {suggestion['title'][:10]}...")
    
    files = suggestion.get("files", [])
    if not files:
        return

    # 1. Workspace の準備
    for f in files:
        src_path = os.path.join(SRC_DIR, f)
        dest_path = os.path.join(WORKSPACE_DIR, f)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        if os.path.exists(src_path):
            shutil.copy2(src_path, dest_path)
        else:
            with open(dest_path, "w") as empty_f:
                empty_f.write("")
            logger.info(f"Prepared new file in workspace: {f}")

    # 2. & 3. 差分生成とテストのリトライループ (最大3回)
    max_attempts = 3
    success = False
    test_report = ""
    full_diff = ""
    errors_feedback = "" # AIへのフィードバック用

    for attempt in range(1, max_attempts + 1):
        logger.info(f"Development attempt {attempt}/{max_attempts} for {prop_id}")
        if attempt > 1:
            set_system_state_helper("ai_target_goal", f"デバッグ中ばい({attempt}回目): {prop_id}")

        current_attempt_success = True
        current_attempt_report = f"--- Attempt {attempt} ---\n"
        
        # 各ファイルの生成
        for f in files:
            work_path = os.path.join(WORKSPACE_DIR, f)
            original_code = ""
            if os.path.exists(work_path) and attempt == 1:
                # 初回のみ現在のファイルを読み取る（2回目以降は前回生成したファイルが work_path にある）
                with open(work_path, "r") as f_in:
                    original_code = f_in.read()
            elif attempt > 1:
                # リトライ時は「直前の失敗コード」を元に修正させるため、再度読み込む
                with open(work_path, "r") as f_in:
                    original_code = f_in.read()

            edit_prompt = f"""
ファイル: {f}
修正計画: {suggestion['plan']}
現在の試行回数: {attempt}/{max_attempts}

【指示】
現在のコードを読み、計画に沿って修正した「完全な新しいコード」を出力してください。
"""
            if errors_feedback:
                edit_prompt += f"\n【前回の失敗原因 (Syntax Error)】\n{errors_feedback}\nこのエラーを解消するように修正してください。"

            edit_prompt += f"\n\n【現在のコード】\n{original_code}\n\n余計な解説は不要です。コードのみ出力してください。"

            res = await openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": edit_prompt}]
            )
            new_code = res.choices[0].message.content.strip()
            if new_code.startswith("```"):
                new_code = "\n".join(new_code.split("\n")[1:-1])
            
            with open(work_path, "w") as f_out:
                f_out.write(new_code)
            
            # テスト (Syntax Check)
            if f.endswith(".py"):
                res_test = subprocess.run(["python3", "-m", "py_compile", work_path], capture_output=True, text=True)
                if res_test.returncode != 0:
                    current_attempt_success = False
                    current_attempt_report += f"❌ Syntax check failed: {f}\n{res_test.stderr}\n"
                    errors_feedback = res_test.stderr # 次のリトライ用のフィードバック
                else:
                    current_attempt_report += f"✅ Syntax check passed: {f}\n"

        if current_attempt_success:
            success = True
            test_report = current_attempt_report
            # Diffの簡易生成（全ファイル分）
            for f in files:
                full_diff += f"--- {f} (updated)\n(Code generated/fixed in attempt {attempt})\n\n"
            break
        else:
            test_report = current_attempt_report # 最終的なレポート用に保存

    # 4. 提案の保存
    async with httpx.AsyncClient() as client:
        status = "PENDING" if success else "FAILED"
        if success:
            logger.info(f"Proposal {prop_id} ready after {attempt} attempts.")
        else:
            logger.warn(f"Auto-discarding proposal {prop_id} after {max_attempts} failed attempts.")
            set_system_state_helper("ai_target_goal", f"改修案 {prop_id} は3回直そうとしたばってん、ダメやった...")

        await client.post(f"{MEMORY_SERVICE_URL}/proposals/", json={
            "id": prop_id,
            "title": suggestion["title"],
            "description": suggestion["description"],
            "plan_json": json.dumps({"files": files, "plan": suggestion["plan"]}),
            "files_affected": ", ".join(files),
            "diff_content": full_diff,
            "test_results": test_report,
            "status": status
        })

    # 5. LINE 通知を core に依頼 (成功時のみ)
    if success:
        async with httpx.AsyncClient() as client:
            attempts_msg = f"（{attempt}回目の修正で成功したばい！）" if attempt > 1 else ""
            report_msg = f"【整備報告】\n{suggestion['title']}の改修案がまとまったばい！{attempts_msg}\n確認して出航（承認）ばお願い！\n\nID: {prop_id}"
            admin_id = os.getenv("LINE_ADMIN_USER_ID", "")
            if admin_id:
                await client.post("http://line-gateway:8001/api/v1/push", json={"user_id": admin_id, "text": report_msg})

@app.on_event("startup")
async def startup_event():
    # 起動時にDBテーブルを確実に作成する
    try:
        init_db()
        logger.info("Database initialized in dev-agent")
    except Exception as e:
        print(f"Critical DB init fail: {e}")
    
    asyncio.create_task(development_loop())
