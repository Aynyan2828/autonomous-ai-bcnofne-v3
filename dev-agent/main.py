import os
import sys
import asyncio
import httpx
import shutil
import subprocess
import json
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from openai import AsyncOpenAI

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.logger import ShipLogger

logger = ShipLogger("dev-agent")
app = FastAPI(title="shipOS Dev Agent")
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SRC_DIR = "/app/src"
WORKSPACE_DIR = "/app/workspace"
MEMORY_SERVICE_URL = "http://memory-service:8003"

class ApplyRequest(BaseModel):
    proposal_id: str

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "dev-agent"}

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
    
    try:
        # 1. 提案内容の取得
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{MEMORY_SERVICE_URL}/proposals/{proposal_id}")
            if r.status_code != 200:
                logger.error(f"Proposal {proposal_id} not found in memory-service")
                return
            proposal = r.json()

        # 2. バックアップ (Git commit)
        # 本来はホスト側で行うのが安全だが、コンテナ内からも git 操作ができる前提
        try:
            subprocess.run(["git", "-C", SRC_DIR, "add", "."], check=True)
            subprocess.run(["git", "-C", SRC_DIR, "commit", "-m", f"pre-apply backup for {proposal_id}"], check=True)
            logger.info("Backup commit created.")
        except Exception as e:
            logger.warn(f"Backup commit failed (maybe no changes?): {e}")

        # 3. 反映実行 (workspace から src へコピー)
        # 固定の workspace 構造を想定
        # 簡易化のため、plan_json に含まれるファイルリストを元にコピーする
        plan = json.loads(proposal.get("plan_json", "{}"))
        files = plan.get("files", [])
        
        for f_path in files:
            src_full = os.path.join(SRC_DIR, f_path)
            work_full = os.path.join(WORKSPACE_DIR, f_path)
            if os.path.exists(work_full):
                os.makedirs(os.path.dirname(src_full), exist_ok=True)
                shutil.copy2(work_full, src_full)
                logger.info(f"Applied change to {f_path}")

        # 4. ステータス更新
        async with httpx.AsyncClient() as client:
            await client.patch(f"{MEMORY_SERVICE_URL}/proposals/{proposal_id}", json={"status": "APPLIED"})
        
        logger.info(f"Apply completed for {proposal_id}. Awaiting service restart...")
        
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
    await asyncio.sleep(30) # 起動直後は少し待つ
    logger.info("Autonomous Development Loop started.")
    
    while True:
        try:
            # (1) Observe & Think
            # ログやメトリクスを収集し、OpenAI に相談
            await run_autonomous_observation()
            
        except Exception as e:
            logger.error(f"Development loop error: {e}")
            
        await asyncio.sleep(3600) # 1時間おき

async def run_autonomous_observation():
    """観測と改善案の生成"""
    logger.info("Observing system for improvements...")
    
    # 1. データの収集
    async with httpx.AsyncClient() as client:
        # 直近ログ
        mem_resp = await client.get(f"{MEMORY_SERVICE_URL}/summary")
        brain_context = mem_resp.json().get("summary", "") if mem_resp.status_code == 200 else "N/A"
        
        # 現在の提案（PENDING が多すぎればスキップ）
        prop_resp = await client.get(f"{MEMORY_SERVICE_URL}/proposals/", params={"status": "PENDING"})
        pending_count = len(prop_resp.json()) if prop_resp.status_code == 200 else 0
        
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
        logger.error(f"Observation / Suggestion error: {e}")

async def process_suggestion(suggestion):
    """提案された内容を実際に workspace で実装・テストする"""
    prop_id = suggestion["id"]
    logger.info(f"Processing suggestion: {prop_id} - {suggestion['title']}")
    
    files = suggestion.get("files", [])
    if not files:
        return

    # 1. Workspace の準備 (src からコピー)
    for f in files:
        src_path = os.path.join(SRC_DIR, f)
        dest_path = os.path.join(WORKSPACE_DIR, f)
        if os.path.exists(src_path):
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copy2(src_path, dest_path)

    # 2. 差分生成 (OpenAI にコード修正を依頼)
    # ここでは簡易化のため、各ファイルに対して修正を依頼する
    for f in files:
        work_path = os.path.join(WORKSPACE_DIR, f)
        if not os.path.exists(work_path): continue
        
        with open(work_path, "r") as f_in:
            original_code = f_in.read()
            
        edit_prompt = f"""
ファイル: {f}
修正計画: {suggestion['plan']}

現在のコードを読み、計画に沿って修正した「完全な新しいコード」を出力してください。
余計な解説は不要です。コードのみ出力してください。

【元のコード】
{original_code}
"""
        res = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": edit_prompt}]
        )
        new_code = res.choices[0].message.content.strip()
        # Markdownのデコレーションを剥ぎ取る
        if new_code.startswith("```"):
            new_code = "\n".join(new_code.split("\n")[1:-1])
            
        with open(work_path, "w") as f_out:
            f_out.write(new_code)

    # 3. テスト (Syntax Check)
    test_report = ""
    success = True
    for f in files:
        work_path = os.path.join(WORKSPACE_DIR, f)
        if f.endswith(".py"):
            res = subprocess.run(["python3", "-m", "py_compile", work_path], capture_output=True, text=True)
            if res.returncode != 0:
                success = False
                test_report += f"❌ Syntax check failed: {f}\n{res.stderr}\n"
            else:
                test_report += f"✅ Syntax check passed: {f}\n"

    # 4. 提案の保存
    async with httpx.AsyncClient() as client:
        await client.post(f"{MEMORY_SERVICE_URL}/proposals/", json={
            "id": prop_id,
            "title": suggestion["title"],
            "description": suggestion["description"],
            "plan_json": json.dumps({"files": files, "plan": suggestion["plan"]}),
            "files_affected": ", ".join(files),
            "test_results": test_report
        })

    # 5. LINE 通知を core に依頼
    if success:
        # core サービスに通知（本来は LINE gateway 直でも良いが、core が人格を担当）
        async with httpx.AsyncClient() as client:
            # 内部的な通知システム（仮）
            report_msg = f"【整備報告】\n{suggestion['title']}の改修案がまとまったばい！\nテストもパスしたけん、確認して出航（承認）ばお願い！\n\nID: {prop_id}\n\n「詳細 {prop_id}」で中身ば見れるよ。"
            # 管理者にプッシュ送信
            admin_id = os.getenv("LINE_ADMIN_USER_ID", "")
            if admin_id:
                # core の push エンドポイントまたは直接 line-gateway
                await client.post("http://line-gateway:8001/api/v1/push", json={"user_id": admin_id, "text": report_msg})

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(development_loop())
