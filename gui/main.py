import os
import sys
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = FastAPI(title="shipOS GUI Dashboard")

# 静的ファイルとテンプレートの設定
assets_dir = os.path.join(os.path.dirname(__file__), "assets")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")

app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
templates = Jinja2Templates(directory=templates_dir)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "gui"}

@app.get("/", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    system_states = []
    billing_data = {
        "is_special_day": False, 
        "current_cost_jpy": 0.0, 
        "total_cost_jpy": 0.0,
        "request_count": 0, 
        "alert_level": "UNKNOWN"
    }
    logs = []
    proposals = []

    try:
        from shared.database import SessionLocal
        from shared.models import SystemState, SystemLog, AutoImprovementProposal
        db = SessionLocal()
        
        # システム状態の取得
        states = db.query(SystemState).all()
        system_states = [{"key": s.key, "value": s.value} for s in states]
        
        # ログの取得
        log_entries = db.query(SystemLog).order_by(SystemLog.created_at.desc()).limit(100).all()
        for entry in log_entries:
            created = entry.created_at
            time_str = created.strftime("%m/%d %H:%M") if created else "??"
            logs.append({
                "time": time_str,
                "service": entry.service_name or "??",
                "level": entry.level or "INFO",
                "message": entry.message or ""
            })
        
        # 改修案の取得
        proposals_raw = db.query(AutoImprovementProposal).order_by(AutoImprovementProposal.created_at.desc()).limit(10).all()
        for p in proposals_raw:
            proposals.append({
                "id": p.id,
                "status": p.status,
                "title": p.title,
                "description": p.description,
                "reason": p.target_selection_reason,
                "diff": p.diff_content,
                "files_affected": p.files_affected or ""
            })
        
        db.close()

        # 課金情報の取得
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get("http://billing-guard:8002/status", timeout=2.0)
                if resp.status_code == 200:
                    billing_data.update(resp.json())
        except Exception as e:
            print(f"Billing access error: {e}")

        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "system_states": system_states,
                "billing_data": billing_data,
                "logs": logs,
                "proposals": proposals
            }
        )
    except Exception as e:
        import traceback
        error_info = traceback.format_exc()
        return HTMLResponse(content=f"<h1>AYN Emergency Dashboard (Error)</h1><pre>{error_info}</pre>", status_code=500)

@app.get("/api/workspace-file")
async def get_workspace_file(path: str):
    """(Security Note: workspace のみ参照可能に制限する)"""
    base_dir = os.path.abspath("/app/workspace")
    target_path = os.path.abspath(os.path.join(base_dir, path))
    
    if not target_path.startswith(base_dir):
        return {"error": "不正なファイルパスへのアクセスばい！"}
    
    if not os.path.exists(target_path):
        return {"error": "まだファイルが作成されてないか、見つからんやったよ！"}
        
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()
            return {"content": content}
    except Exception as e:
        return {"error": f"ファイルの読み込みに失敗したばい：{str(e)}"}

INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "aynyan-secret-2828")

@app.post("/api/proposals/{proposal_id}/apply")
async def apply_proposal_api(proposal_id: str):
    """(Security Note: INTERNAL_TOKENを使ってdev-agentを叩く)"""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"http://dev-agent:8013/apply/{proposal_id}",
                headers={"X-Internal-Token": INTERNAL_TOKEN},
                timeout=10.0
            )
            if resp.status_code == 200:
                return {"status": "success", "message": f"{proposal_id} の適用を開始したばい！再起動ば待っとってね！"}
            else:
                return {"status": "error", "message": f"適用に失敗したかも... ステータスコード: {resp.status_code}"}
    except Exception as e:
        return {"status": "error", "message": f"通信エラーが発生したばい：{e}"}

@app.post("/api/proposals/{proposal_id}/reject")
async def reject_proposal_api(proposal_id: str):
    """(Security Note: DB(memory-service)を直接更新してREJECTにする)"""
    try:
        async with httpx.AsyncClient() as client:
            u_resp = await client.patch(f"http://memory-service:8003/proposals/{proposal_id}", json={"status": "REJECTED"})
            if u_resp.status_code == 200:
                return {"status": "success", "message": f"{proposal_id} の改修案を破棄したばい。"}
            return {"status": "error", "message": "破棄データの更新に失敗したばい...。"}
    except Exception as e:
        return {"status": "error", "message": f"通信エラーが発生したばい：{e}"}

from datetime import datetime

@app.get("/api/public-logs")
async def get_public_logs():
    """/mnt/hdd/logs/public 以下のファイルをリストアップする"""
    base_dir = "/mnt/hdd/logs/public"
    logs = []
    if not os.path.exists(base_dir):
        return {"logs": []}
    
    try:
        for cat in ["voyage_log", "evolution_log"]:
            cat_dir = os.path.join(base_dir, cat)
            if os.path.exists(cat_dir):
                files = os.listdir(cat_dir)
                for f in files:
                    if f.endswith(".md"):
                        fpath = os.path.join(cat_dir, f)
                        mtime = os.path.getmtime(fpath)
                        mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                        logs.append({
                            "category": cat,
                            "name": f,
                            "mtime": mtime_str,
                            "ts": mtime
                        })
        # 新しい順にソート
        logs.sort(key=lambda x: x["ts"], reverse=True)
        return {"logs": logs[:20]}
    except Exception as e:
        return {"error": str(e), "logs": []}

@app.get("/api/public-log-content")
async def get_public_log_content(path: str):
    """公開ログの内容を取得する"""
    base_dir = "/mnt/hdd/logs/public"
    target_path = os.path.abspath(os.path.join(base_dir, path))
    
    if not target_path.startswith(os.path.abspath(base_dir)):
        return {"error": "不正なファイルパスばい！"}
    
    if not os.path.exists(target_path):
        return {"error": "ファイルが見つからんやったよ！"}
        
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()
            return {"content": content}
    except Exception as e:
        return {"error": f"読み込み失敗：{str(e)}"}
