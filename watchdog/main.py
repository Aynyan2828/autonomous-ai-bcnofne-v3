import os
import asyncio
import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import SessionLocal
from shared.models import SystemLog
from shared.logger import ShipLogger

logger = ShipLogger("watchdog")

app = FastAPI(title="shipOS Watchdog")

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
                    # ヘルスチェックのタイムアウトは短めに設定
                    response = await client.get(service["url"], timeout=3.0)
                    if response.status_code != 200:
                        log_event("WARN", f"サービス {service['name']} が異常を報告しました。Status: {response.status_code}")
                except httpx.RequestError as exc:
                    log_event("ERROR", f"サービス {service['name']} への接続に失敗しました。ダウンしている可能性があります。（{exc}）")
                except Exception as e:
                    log_event("ERROR", f"未知の監視エラー ({service['name']}): {e}")
            
            # 1分おきに監視
            await asyncio.sleep(60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(monitor_services())
    yield
    task.cancel()

app.router.lifespan_context = lifespan

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "watchdog"}
