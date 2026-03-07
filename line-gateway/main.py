import os
import httpx
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from pydantic import BaseModel

app = FastAPI(title="shipOS LINE Gateway")

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "dummy_token")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "dummy_secret")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

CORE_URL = "http://core:8000"

class PushMessageRequest(BaseModel):
    user_id: str
    text: str

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "line-gateway"}

@app.post("/webhook")
async def callback(request: Request, background_tasks: BackgroundTasks):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_str = body.decode("utf-8")

    try:
        # 署名検証は実際には必須だが、MVPでローカルテストしやすいよう一旦緩和可能
        handler.handle(body_str, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """ユーザーからのメッセージを受信し、coreへ転送する"""
    text = event.message.text
    user_id = event.source.user_id
    reply_token = event.reply_token

    # Coreサービスに非同期で投げて処理を委譲する (ここで待つとLINEがタイムアウトするため)
    import asyncio
    asyncio.create_task(forward_to_core(text, user_id, reply_token))

async def forward_to_core(text: str, user_id: str, reply_token: str):
    """受信したメッセージをCoreに転送"""
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{CORE_URL}/api/v1/message",
                json={
                    "text": text,
                    "user_id": user_id,
                    "reply_token": reply_token,
                    "source": "LINE"
                },
                timeout=5.0
            )
    except Exception as e:
        print(f"Failed to forward message to core: {e}")

@app.post("/api/v1/reply")
def reply_message(reply_token: str, text: str):
    """Coreから呼ばれ、LINEユーザーに返信するエンドポイント"""
    try:
        line_bot_api.reply_message(reply_token, TextSendMessage(text=text))
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/push")
def push_message(req: PushMessageRequest):
    """Coreから呼ばれ、AIから能動的にLINE通知するエンドポイント"""
    try:
        line_bot_api.push_message(req.user_id, TextSendMessage(text=req.text))
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
