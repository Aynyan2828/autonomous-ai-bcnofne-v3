import os
import asyncio
import httpx
import docker
from fastapi import FastAPI, BackgroundTasks, HTTPException, Header, Depends
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import SessionLocal
from shared.models import SystemLog
from shared.logger import ShipLogger

logger = ShipLogger("watchdog")

app = FastAPI(title="BCNOFNe Watchdog")
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "aynyan-secret-2828")

def verify_internal_token(x_internal_token: str = Header(None)):
    if not x_internal_token or x_internal_token != INTERNAL_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid or missing Internal Token")
    return True

SERVICES_TO_MONITOR = [
    {"name": "core", "url": "http://core:8000/health"},
    {"name": "line-gateway", "url": "http://line-gateway:8001/health"},
    {"name": "billing-guard", "url": "http://billing-guard:8002/health"},
    {"name": "memory-service", "url": "http://memory-service:8003/health"},
    {"name": "diary-service", "url": "http://diary-service:8004/health"},
    {"name": "dev-agent", "url": "http://dev-agent:8013/health"},
]

def log_event(level: str, message: str):
    if level == "INFO":
        logger.info(message)
    elif level == "WARN":
        logger.warn(message)
    elif level == "CRITICAL" or level == "ERROR":
        logger.error(message)

async def monitor_services():
    async with httpx.AsyncClient() as client:
        while True:
            for service in SERVICES_TO_MONITOR:
                try:
                    # ヘルスチェックのタイムアウトは、LLM処理中を考慮して少し長めに設定
                    response = await client.get(service["url"], timeout=10.0)
                    if response.status_code != 200:
                        log_event("WARN", f"サービス {service['name']} が異常を報告しました。Status: {response.status_code}")
                except httpx.RequestError as exc:
                    log_event("ERROR", f"サービス {service['name']} への接続に失敗しました。ダウンしている可能性があります。（{exc}）")
                except Exception as e:
                    log_event("ERROR", f"未知の監視エラー ({service['name']}): {e}")
            
            # 1分おきに監視
            await asyncio.sleep(60)

async def execute_restart():
    """実際のコンテナ再起動処理"""
    logger.info("Executing system-wide container restart...")
    try:
        client = docker.from_env()
        # shipos- で始まるコンテナを全て取得
        containers = client.containers.list(all=True, filters={"name": "shipos-"})
        
        # 自身 (watchdog) 以外を先に再起動
        for container in containers:
            if "watchdog" in container.name:
                continue
            logger.info(f"Restarting container: {container.name}")
            container.restart(timeout=10)
        
        # 最後に自身を再起動
        logger.info("Restarting watchdog last...")
        watchdog = client.containers.get("shipos-watchdog")
        watchdog.restart(timeout=5)
    except Exception as e:
        logger.error(f"Restart execution failed: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(monitor_services())
    yield
    task.cancel()

app.router.lifespan_context = lifespan

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "watchdog"}

@app.post("/restart")
async def restart_system(background_tasks: BackgroundTasks, _: bool = Depends(verify_internal_token)):
    """
    全コンテナを再起動するエンドポイント
    """
    logger.info("Restart request received.")
    background_tasks.add_task(execute_restart)
    return {"status": "accepted", "message": "全システムを再起動するばい。ちょっと待っとってね。"}
