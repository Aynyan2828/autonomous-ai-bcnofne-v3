import os
import sys
import asyncio
import httpx
import shutil
import subprocess
import json
import uuid
import traceback
import difflib
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, BackgroundTasks, HTTPException, Header
from pydantic import BaseModel
from openai import AsyncOpenAI

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import init_db
from shared.logger import ShipLogger
from shared.database import SessionLocal
from shared.models import SystemState, SystemLog, AutoImprovementProposal
from sqlalchemy import func

VERSION = "v3.3.0"
print(f"AYN {VERSION} STARTING... (CWD: {os.getcwd()})")

logger = ShipLogger("dev-agent")
app = FastAPI(title="BCNOFNe Dev Agent")
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def _report_billing(response, model: str = "gpt-4o-mini"):
    """OpenAI 呼び出し後に billing-guard に使用量を報告する"""
    try:
        usage = getattr(response, 'usage', None)
        input_tokens = usage.prompt_tokens if usage else 500
        output_tokens = usage.completion_tokens if usage else 500
        async with httpx.AsyncClient() as client:
            await client.post("http://billing-guard:8002/record",
                            params={"model": model, "input_tokens": input_tokens, "output_tokens": output_tokens},
                            timeout=2.0)
    except Exception:
        pass

SRC_DIR = "/app/src"
WORKSPACE_DIR = "/app/workspace"
MEMORY_SERVICE_URL = "http://memory-service:8003"
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "aynyan-secret-2828")
ALLOWED_SERVICES = ["core", "line-gateway", "watchdog", "dev-agent"]

def verify_internal_token(x_internal_token: str = Header(None)):
    if not x_internal_token or x_internal_token != INTERNAL_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid or missing Internal Token")
    return True

def is_git_dirty() -> bool:
    """Git に未コミットの変更があるかチェック"""
    try:
        res = subprocess.run(["git", "-C", SRC_DIR, "status", "--porcelain"], 
                             capture_output=True, text=True, check=True)
        return len(res.stdout.strip()) > 0
    except:
        return False

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
                             headers={"X-Internal-Token": INTERNAL_TOKEN},
                             timeout=5.0)
        except Exception as e:
            logger.error(f"Failed to send push notification: {e}")

# --- AI Intelligence Helpers ---

async def get_24h_failure_summary() -> str:
    """直近24時間の障害統計を構造化テキストで返す"""
    db = SessionLocal()
    try:
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        
        # ERROR/WARN 件数
        counts = db.query(SystemLog.level, func.count(SystemLog.id))\
                   .filter(SystemLog.created_at >= since)\
                   .filter(SystemLog.level.in_(["ERROR", "WARN"]))\
                   .group_by(SystemLog.level).all()
        counts_dict = {lv: cnt for lv, cnt in counts}
        
        # 例外トップ3 (メッセージの先頭行で集計)
        # 簡易的に最初の20文字程度でグループ化
        errors = db.query(SystemLog.message)\
                   .filter(SystemLog.created_at >= since)\
                   .filter(SystemLog.level == "ERROR").all()
        error_msgs = [m[0].split('\n')[0][:50] for m in errors]
        top_exceptions = {}
        for m in error_msgs:
            top_exceptions[m] = top_exceptions.get(m, 0) + 1
        sorted_expr = sorted(top_exceptions.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # サービス別エラー件数
        service_counts = db.query(SystemLog.service_name, func.count(SystemLog.id))\
                           .filter(SystemLog.created_at >= since)\
                           .filter(SystemLog.level == "ERROR")\
                           .group_by(SystemLog.service_name).all()
        
        # 最近失敗した提案
        failed_props = db.query(AutoImprovementProposal)\
                         .filter(AutoImprovementProposal.status == "FAILED")\
                         .order_by(AutoImprovementProposal.created_at.desc()).limit(3).all()
        
        summary = "【直近24時間の障害統計】\n"
        summary += f"- エラー件数: {counts_dict.get('ERROR', 0)}, 警告件数: {counts_dict.get('WARN', 0)}\n"
        summary += "- 主要な例外:\n" + "\n".join([f"  * {m} ({c}回)" for m, c in sorted_expr]) + "\n"
        summary += "- サービス別エラー:\n" + "\n".join([f"  * {s}: {c}件" for s, c in service_counts]) + "\n"
        summary += "- 最近失敗した改修案:\n" + "\n".join([f"  * {p.id}: {p.title} ({p.last_error_summary})" for p in failed_props])
        return summary
    except Exception as e:
        logger.error(f"Failed to get failure summary: {e}")
        return "障害統計の取得に失敗しました。"
    finally:
        db.close()

def generate_repo_map() -> str:
    """リポジトリの軽量マップを生成する"""
    map_lines = ["【リポジトリマップ】"]
    exclude_dirs = [".git", "__pycache__", "workspace", "data", "venv", "node_modules"]
    
    for root, dirs, files in os.walk(SRC_DIR):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        rel_path = os.path.relpath(root, SRC_DIR)
        if rel_path == ".":
            rel_path = ""
        
        for f in files:
            if not f.endswith((".py", ".sh", ".yml", ".md", ".dockerfile", "Dockerfile")):
                continue
            
            full_path = os.path.join(root, f)
            display_path = os.path.join(rel_path, f)
            
            # 先頭行からコメント（説明）を抽出
            desc = ""
            try:
                with open(full_path, "r", encoding="utf-8") as file_in:
                    first_line = file_in.readline().strip()
                    desc_text = first_line.replace('"""', '').replace("'''", "").strip()
                    if first_line.startswith("#"):
                        desc = f" - {first_line[1:].strip()}"
                    elif '"""' in first_line or "'''" in first_line:
                        desc = f" - {desc_text}"
            except:
                pass
            
            map_lines.append(f"- {display_path}{desc}")
            
    return "\n".join(map_lines[:50]) # あまりに多い場合は制限

async def get_relevant_context(target_file: str, plan: str) -> str:
    """修正対象に関連する周辺コード（シグネチャ、モデル定義等）を抽出する"""
    context = []
    
    # 1. 共通モデル (models.py) の定義は常に有用
    models_path = os.path.join(SRC_DIR, "shared/models.py")
    if os.path.exists(models_path) and "models" in plan.lower():
        try:
            with open(models_path, "r") as f:
                # クラス定義のみ抽出（簡易）
                lines = f.readlines()
                classes = [l.strip() for l in lines if l.startswith("class ")]
                context.append("【shared/models.py クラス定義】\n" + "\n".join(classes))
        except: pass

    # 2. ターゲットファイルが import している自作モジュールのシグネチャを抽出
    src_path = os.path.join(SRC_DIR, target_file)
    if os.path.exists(src_path):
        try:
            with open(src_path, "r") as f:
                lines = f.readlines()
                imports = [l for l in lines if "from " in l or "import " in l]
                # 自作モジュールっぽいものを探して、そのファイルの関数一覧を出す
                for imp in imports:
                    if "shared." in imp or "core." in imp:
                        # 雑な推論でパスを特定
                        parts = imp.split()
                        mod_name = ""
                        if "from" in parts:
                            mod_name = parts[parts.index("from")+1]
                        
                        rel_mod_path = mod_name.replace(".", "/") + ".py"
                        full_mod_path = os.path.join(SRC_DIR, rel_mod_path)
                        if os.path.exists(full_mod_path):
                            with open(full_mod_path, "r") as mf:
                                m_lines = mf.readlines()
                                sigs = [l.strip() for l in m_lines if l.strip().startswith(("def ", "class "))]
                                context.append(f"【{rel_mod_path} の定義要約】\n" + "\n".join(sigs[:10]))
        except: pass

    return "\n\n".join(context)

class ApplyRequest(BaseModel):
    proposal_id: str

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "dev-agent"}

@app.post("/sync")
async def sync_repository(_: bool = Depends(verify_internal_token)):
    """
    GitHub から最新のソースコードを取得するエンドポイント
    """
    if is_git_dirty():
        msg = "⚠️ Git に未コミットの変更があるため、同期を中止したばい。マスターに確認してね。"
        await send_push_notification(msg)
        return {"status": "error", "message": msg}
    try:
        # 1. Git pull 実行
        logger.info("Starting git pull from origin main...")
        res = subprocess.run(
            ["git", "-C", SRC_DIR, "pull", "--rebase", "origin", "main"],
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

@app.post("/update")
async def update_system(background_tasks: BackgroundTasks, _: bool = Depends(verify_internal_token)):
    """chown + git pull + restart を一括実行するエンドポイント"""
    if is_git_dirty():
        msg = "⚠️ Git に未コミットの変更があるため、アップデートを中止したばい。"
        await send_push_notification(msg)
        return {"status": "error", "message": msg}
    background_tasks.add_task(execute_full_update)
    return {"status": "queued", "message": "フルアップデートを開始するばい！"}

async def execute_full_update():
    """chown → git checkout → git pull → watchdog restart の一括実行"""
    logger.info("Full update started (triggered via LINE)")
    steps = []
    
    try:
        # 1. git パーミッション修正
        _fix_git_permissions()
        res = subprocess.run(["chown", "-R", "1000:1000", SRC_DIR],
                           capture_output=True, text=True, check=False)
        steps.append(f"chown: {'OK' if res.returncode == 0 else 'SKIP'}")
        
        # 2. ローカル変更を破棄
        subprocess.run(["git", "config", "--system", "--add", "safe.directory", SRC_DIR], check=False)
        res = subprocess.run(["git", "-C", SRC_DIR, "checkout", "--", "."],
                           capture_output=True, text=True, check=False)
        steps.append(f"git checkout: {'OK' if res.returncode == 0 else res.stderr.strip()[:50]}")
        
        # 3. git pull
        res = subprocess.run(["git", "-C", SRC_DIR, "pull", "--rebase", "origin", "main"],
                           capture_output=True, text=True, timeout=60, check=False)
        if res.returncode == 0:
            steps.append("git pull: OK")
        else:
            steps.append(f"git pull: FAIL - {res.stderr.strip()[:80]}")
            await send_push_notification(f"⚠️ アップデート失敗したばい。\n" + "\n".join(steps))
            return
        
        # 4. パーミッション再修正
        _fix_git_permissions()
        
        # 5. watchdog に再起動を依頼
        logger.info("Update pull complete. Triggering restart via watchdog...")
        steps.append("restart: triggered")
        
        await send_push_notification(
            f"✅ アップデート完了したばい！\n" + "\n".join(steps) + "\n\n再起動中やけん、30秒くらい待っとってね！🚢💨"
        )
        
        # watchdog に再起動をリクエスト
        async with httpx.AsyncClient() as client:
            try:
                await client.post("http://watchdog:8005/restart", 
                                 headers={"X-Internal-Token": INTERNAL_TOKEN},
                                 timeout=5.0)
            except Exception:
                pass  # watchdog が再起動するので接続切れは想定内
    
    except Exception as e:
        logger.error(f"Full update error: {e}")
        await send_push_notification(f"⚠️ アップデート中にエラー: {e}")

@app.post("/apply/{proposal_id}")
async def apply_proposal(proposal_id: str, background_tasks: BackgroundTasks, _: bool = Depends(verify_internal_token)):
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
            subprocess.run(["git", "config", "--system", "--add", "safe.directory", SRC_DIR], check=True)
            subprocess.run(["git", "config", "--system", "user.email", "ayn@shipos.local"], check=True)
            subprocess.run(["git", "config", "--system", "user.name", "AYN"], check=True)
            
            subprocess.run(["git", "-C", SRC_DIR, "add", "."], check=True)
            res = subprocess.run(["git", "-C", SRC_DIR, "commit", "-m", f"pre-apply backup for {proposal_id}", "--allow-empty"], 
                                 capture_output=True, text=True, check=True)
            logger.info(f"Backup commit created successfully: {res.stdout.strip()}")
        except subprocess.CalledProcessError as e:
            logger.warn(f"Backup commit skipped or failed (Git Error 128?): {e.stderr.strip()}")
        except Exception as e:
            logger.warn(f"Backup commit fatal error: {repr(e)}")
        finally:
            # ★恒久対策: git 操作後に .git の所有権をホスト側ユーザー (UID 1000 = pi) に戻す
            _fix_git_permissions()

        # 3. 反映実行前の最終検証 (Pre-verify in workspace)
        plan = json.loads(proposal.get("plan_json", "{}"))
        files = plan.get("files", [])
        
        for f_path in files:
            work_full = os.path.join(WORKSPACE_DIR, f_path)
            if f_path.endswith(".py") and os.path.exists(work_full):
                res_test = subprocess.run(["python3", "-m", "py_compile", work_full], capture_output=True, text=True)
                if res_test.returncode != 0:
                    logger.error(f"Final verification FAILED for {f_path} in proposal {proposal_id}")
                    await send_push_notification(f"⚠️ 改修案 {proposal_id} の適用を中止したばい。最終検証でエラーが出たよ：\n{res_test.stderr}")
                    async with httpx.AsyncClient() as client:
                        await client.patch(f"{MEMORY_SERVICE_URL}/proposals/{proposal_id}", 
                                         json={"status": "FAILED", "failure_stage": "apply", "last_error_summary": res_test.stderr})
                    return

        # 4. 反映実行 (workspace から src へコピー)
        for f_path in files:
            src_full = os.path.join(SRC_DIR, f_path)
            work_full = os.path.join(WORKSPACE_DIR, f_path)
            if os.path.exists(work_full):
                logger.info(f"Source file found in workspace: {work_full}")
                os.makedirs(os.path.dirname(src_full), exist_ok=True)
                shutil.copy2(work_full, src_full)
                # コピーしたファイルの所有権もホスト側に合わせる
                try:
                    os.chown(src_full, 1000, 1000)
                except Exception:
                    pass
                logger.info(f"Successfully applied change to {f_path}")
            else:
                logger.error(f"Source file NOT FOUND in workspace: {work_full} (Proposal: {proposal_id})")

        # 4. ステータス更新
        async with httpx.AsyncClient() as client:
            await client.patch(f"{MEMORY_SERVICE_URL}/proposals/{proposal_id}", json={"status": "APPLIED"})
        
        logger.info(f"Apply completed for {proposal_id}. Awaiting service restart...")
        await send_push_notification(f"マスター、改修案 {proposal_id} の整備（適用）が完了したばい！正常に反映されたけん、安心してね。")
        
        # 最後に全体の権限を修正
        _fix_git_permissions()

    except Exception as e:
        logger.error(f"Apply fatal error for {proposal_id}: {e}")
        async with httpx.AsyncClient() as client:
            await client.patch(f"{MEMORY_SERVICE_URL}/proposals/{proposal_id}", json={"status": "FAILED"})
        _fix_git_permissions()

def _fix_git_permissions():
    """git 操作後に .git ディレクトリの所有権をホスト側 (UID 1000 = pi) に戻す恒久対策"""
    try:
        subprocess.run(["chown", "-R", "1000:1000", os.path.join(SRC_DIR, ".git")],
                       capture_output=True, check=False)
    except Exception as e:
        print(f"[dev-agent] WARN: chown fix failed (non-critical): {e}")

# --- Autonomous Development Loop ---

async def development_loop():
    """
    1時間に1回、システムの状態を観測して改善案を練る自律ループ
    """
    logger.info(f"Autonomous Development Loop started (version: {VERSION})")
    await asyncio.sleep(30) # 他のサービスの起動を待つ
    
    while True:
        next_sleep = 3600
        try:
            # (1) Observe & Think
            # ログやメトリクスを収集し、OpenAI に相談
            result = await run_autonomous_observation()
            if result == "generation_failed":
                next_sleep = 600
            elif result == "memory_error":
                next_sleep = 300
            
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"Development loop error: {e}\n{error_trace}")
            next_sleep = 300
            
        logger.info(f"Loop finished. Sleeping for {next_sleep}s...")
        await asyncio.sleep(next_sleep)

async def safe_get_memory_summary(client):
    """memory-service からの要約取得を指数バックオフ付きで実行"""
    for attempt in range(5):
        try:
            r = await client.get(f"{MEMORY_SERVICE_URL}/summary", timeout=10.0)
            if r.status_code == 200:
                return r.json().get("summary", "")
        except Exception as e:
            wait_time = 2 ** attempt
            logger.warn(f"Failed to fetch memory summary (attempt {attempt+1}): {e}. Retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)
    return "N/A"

async def run_autonomous_observation():
    """観測と改善案の生成"""
    logger.info("Observing system for improvements...")
    set_system_state_helper("ai_target_goal", "システムを観測中ばい...")
    
    # 1. データの収集
    async with httpx.AsyncClient() as client:
        # 直近ログ (指数バックオフ付き)
        brain_context = await safe_get_memory_summary(client)
        if brain_context == "N/A":
            return "memory_error"
        
        # 障害統計とリポジトリマップの取得
        failure_summary = await get_24h_failure_summary()
        repo_map = generate_repo_map()
        
        # 現在の提案（PENDING が多すぎればスキップ）
        try:
            prop_resp = await client.get(f"{MEMORY_SERVICE_URL}/proposals/", params={"status": "PENDING"}, timeout=5.0)
            pending_count = len(prop_resp.json()) if prop_resp.status_code == 200 else 0
        except:
            pending_count = 0
        
    if pending_count >= 3:
        logger.info("Too many pending proposals. Skipping observation.")
        return "skipped"

    # 2. OpenAI による分析
    prompt = f"""
あなたは shipOS の主任整備士 AYN です。システムの健全性と利便性を高めるのが任務です。
現在の脳内コンテキスト、障害統計、およびリポジトリ構成を確認して、改善が必要な箇所を「最大3つ」挙げてください。

【現在の脳内コンテキスト】
{brain_context}

{failure_summary}

{repo_map}

【任務】
1. 障害統計や記憶から、ボトルネックや修正が必要な箇所を特定してください。
2. 修正候補を最大3つ挙げ、それぞれの「選定理由」「自信度(0.0-1.0)」「修正計画」を考えてください。
3. 最も優先度・自信度が高いものをプライマリとして提案してください。

出力は以下の JSON 形式で答えてください：
{{
  "candidates": [
    {{
      "title": "改善のタイトル",
      "description": "なぜこれが必要か (evidence summary)",
      "files": ["修正ファイルパス1", "..."],
      "plan": "具体的な修正内容の指示",
      "reason": "このファイルを選んだ技術的・論理的理由",
      "confidence": 0.9
    }}
  ]
}}
"""
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={ "type": "json_object" }
        )
        res_data = json.loads(response.choices[0].message.content)
        await _report_billing(response, "gpt-4o-mini")
        
        candidates = res_data.get("candidates", [])
        if not candidates:
            return "skipped"

        # 自信度が最も高いものを選択
        suggestion = max(candidates, key=lambda x: x.get("confidence", 0.0))
        
        # IDとメタデータの付与
        suggestion["id"] = f"PROP-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
        suggestion["evidence_summary"] = failure_summary # 統計を証拠として残す
        
        # (3) Plan & (4) Build & (5) Test
        return await process_suggestion(suggestion)

    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Observation / Suggestion error: {e}\n{error_trace}")
        return "generation_failed"

async def process_suggestion(suggestion):
    """提案された内容を実際に workspace で実装・テストする (リトライ機能付き)"""
    prop_id = suggestion["id"]
    logger.info(f"Processing suggestion: {prop_id} - {suggestion['title']}")
    set_system_state_helper("ai_target_goal", f"改修案を作成中ばい: {suggestion['title'][:10]}...")
    
    files = suggestion.get("files", [])
    if not files:
        return "skipped"

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
    full_diff = ""
    errors_feedback_dict = {} # ファイル単位のエラー情報: {path: error_msg}
    attempt_history = []
    last_error_summary = ""

    for attempt in range(1, max_attempts + 1):
        logger.info(f"Development attempt {attempt}/{max_attempts} for {prop_id}")
        if attempt > 1:
            set_system_state_helper("ai_target_goal", f"デバッグ中ばい({attempt}回目): {prop_id}")

        current_attempt_success = True
        current_attempt_files_report = {} # {path: status_msg}
        attempt_log = {"attempt": attempt, "results": {}}
        
        # 各ファイルの生成
        for f in files:
            work_path = os.path.join(WORKSPACE_DIR, f)
            src_path = os.path.join(SRC_DIR, f)
            
            # 元のコード（比較用と生成用）
            original_code = ""
            if os.path.exists(src_path):
                with open(src_path, "r") as f_in:
                    original_code = f_in.read()
            
            # 生成ベースコード（リトライ時は前回の workspace コード）
            base_code_for_ai = original_code
            if attempt > 1 and os.path.exists(work_path):
                with open(work_path, "r") as f_in:
                    base_code_for_ai = f_in.read()

            # 周辺文脈の取得
            relevant_context = await get_relevant_context(f, suggestion["plan"])

            edit_prompt = f"""
ファイル: {f}
修正計画: {suggestion['plan']}
現在の試行回数: {attempt}/{max_attempts}

【周辺文脈 (参考情報)】
{relevant_context}

【指示】
周辺文脈を参考にしつつ、指定されたファイルの「完全な新しいコード」を返してください。
"""
            if errors_feedback_dict:
                edit_prompt += f"\n【前回までのエラー情報 (構造化)】\n{json.dumps(errors_feedback_dict, indent=2, ensure_ascii=False)}\n特に自分が修正担当しているファイルのエラー箇所を重点的に直してください。"

            edit_prompt += f"\n\n【ベースコード】\n{base_code_for_ai}\n\n余計な解説は不要です。コードのみ出力してください。"

            res = await openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": edit_prompt}]
            )
            new_code = res.choices[0].message.content.strip()
            await _report_billing(res, "gpt-4o")
            if new_code.startswith("```"):
                new_code = "\n".join(new_code.split("\n")[1:-1])
            
            with open(work_path, "w") as f_out:
                f_out.write(new_code)
            
            # --- 二段階検証 ---
            file_error = None
            if f.endswith(".py"):
                # Step 1: Syntax Check
                res_syntax = subprocess.run(["python3", "-m", "py_compile", work_path], capture_output=True, text=True)
                if res_syntax.returncode != 0:
                    file_error = f"Syntax Error:\n{res_syntax.stderr}"
                else:
                    # Step 2: Import Check (簡易)
                    env = os.environ.copy()
                    env["PYTHONPATH"] = f"/app:{env.get('PYTHONPATH', '')}"
                    mod_path = f.replace("/", ".").replace(".py", "")
                    res_import = subprocess.run(["python3", "-c", f"import {mod_path}"], 
                                               env=env, capture_output=True, text=True)
                    if res_import.returncode != 0:
                        file_error = f"Import/Runtime Error:\n{res_import.stderr}"

            if file_error:
                current_attempt_success = False
                errors_feedback_dict[f] = file_error
                current_attempt_files_report[f] = "FAILED"
                last_error_summary = f"File {f}: {file_error.splitlines()[0]}"
            else:
                current_attempt_files_report[f] = "PASSED"
                if f in errors_feedback_dict: del errors_feedback_dict[f] 
            
            attempt_log["results"][f] = {"status": current_attempt_files_report[f], "error": file_error}

        attempt_history.append(attempt_log)

        if current_attempt_success:
            success = True
            # Unified Diff の生成
            for f in files:
                work_path = os.path.join(WORKSPACE_DIR, f)
                src_path = os.path.join(SRC_DIR, f)
                old_lines = []
                if os.path.exists(src_path):
                    with open(src_path, "r") as f_in:
                        old_lines = f_in.readlines()
                with open(work_path, "r") as f_in:
                    new_lines = f_in.readlines()
                
                diff = difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{f}", tofile=f"b/{f}")
                full_diff += "".join(diff) + "\n"
            break

    # 4. 提案の保存
    async with httpx.AsyncClient() as client:
        status = "PENDING" if success else "FAILED"
        if success:
            logger.info(f"Proposal {prop_id} ready after {attempt} attempts.")
        else:
            logger.warn(f"Auto-discarding proposal {prop_id} after {max_attempts} failed attempts.")
            set_system_state_helper("ai_target_goal", f"改修案 {prop_id} は3回試行したばってん、ダメやった...")

        await client.post(f"{MEMORY_SERVICE_URL}/proposals/", json={
            "id": prop_id,
            "title": suggestion["title"],
            "description": suggestion["description"],
            "plan_json": json.dumps({"files": files, "plan": suggestion["plan"]}),
            "files_affected": ", ".join(files),
            "diff_content": full_diff,
            "test_results": f"Attempts: {attempt}\nSuccess: {success}\n" + json.dumps(current_attempt_files_report, indent=2),
            "status": status,
            "failure_stage": "verification" if not success else None,
            "failure_count": attempt if not success else 0,
            "last_error_summary": last_error_summary if not success else None,
            "attempt_history": json.dumps(attempt_history, ensure_ascii=False),
            "target_selection_reason": suggestion.get("reason"),
            "confidence": suggestion.get("confidence", 0.0),
            "evidence_summary": suggestion.get("evidence_summary")
        })

    # 5. LINE 通知を core に依頼 (成功時のみ)
    if success:
        async with httpx.AsyncClient() as client:
            attempts_msg = f"（{attempt}回目の修正で成功したばい！）" if attempt > 1 else ""
            report_msg = f"【整備報告】\n{suggestion['title']}の改修案がまとまったばい！{attempts_msg}\n確認して出航（承認）ばお願い！\n\nID: {prop_id}"
            admin_id = os.getenv("LINE_ADMIN_USER_ID", "")
            if admin_id:
                async with httpx.AsyncClient() as client:
                    await client.post("http://line-gateway:8001/api/v1/push", 
                                     json={"user_id": admin_id, "text": report_msg},
                                     headers={"X-Internal-Token": INTERNAL_TOKEN})
    
    return "success" if success else "verification_failed"

@app.on_event("startup")
async def startup_event():
    # 起動時にDBテーブルを確実に作成する
    try:
        init_db()
        logger.info("Database initialized in dev-agent")
    except Exception as e:
        print(f"Critical DB init fail: {e}")
    
    asyncio.create_task(development_loop())
