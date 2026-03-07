import os
import httpx
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel

app = FastAPI(title="shipOS Discord Gateway")

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

class DiscordNotifyRequest(BaseModel):
    message: str
    username: str = "shipOS AYN"

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "discord-gateway"}

async def send_to_discord(message: str, username: str):
    if not DISCORD_WEBHOOK_URL:
        print("[DISCORD] Webhook URL not configured. Message:", message)
        return

    payload = {
        "content": message,
        "username": username
    }
    
    async with httpx.AsyncClient() as client:
        try:
            await client.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5.0)
        except Exception as e:
            print(f"Failed to send to Discord: {e}")

@app.post("/notify")
def notify_discord(req: DiscordNotifyRequest, bg_tasks: BackgroundTasks):
    """Core等から呼び出されるDiscordへのPush通知エンドポイント"""
    bg_tasks.add_task(send_to_discord, req.message, req.username)
    return {"status": "accepted"}
