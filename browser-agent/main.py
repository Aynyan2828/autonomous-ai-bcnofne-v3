import os
import sys
import asyncio
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel

app = FastAPI(title="shipOS Browser Agent")

class ScrapeRequest(BaseModel):
    url: str
    instruction: str = ""

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "browser-agent"}

async def run_playwright_task(url: str, instruction: str):
    """
    Playwrightによる自動操作用スタブ。
    本来はここから Playwright を起動し、指定されたURLで作業を行う。
    Raspberry Pi上で動かす場合はリソース上限やヘッドレスモードの考慮が必要。
    """
    print(f"[BROWSER] Starting task on {url}. Instruction: {instruction}")
    await asyncio.sleep(2)
    print(f"[BROWSER] Completed dummy task on {url}.")

@app.post("/task")
def start_browser_task(req: ScrapeRequest, bg_tasks: BackgroundTasks):
    """Coreから呼び出されるブラウザ作業のエンドポイント"""
    bg_tasks.add_task(run_playwright_task, req.url, req.instruction)
    return {"status": "accepted", "message": f"ブラウザタスクをバックグラウンドで開始したばい。({req.url})"}
