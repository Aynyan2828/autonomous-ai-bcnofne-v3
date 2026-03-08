import os
import sys
from fastapi import FastAPI, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import SessionLocal
from shared.models import SystemState

app = FastAPI(title="BCNOFNe Voice Router")

class SpeakRequest(BaseModel):
    text: str
    override_mode: str = None  # NURSE, OAI, HYB (指定があればそれを使う)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_voice_mode(db: Session) -> str:
    state = db.query(SystemState).filter_by(key="voice_mode").first()
    return state.value if state else "NURSE"

def generate_and_play_audio(text: str, mode: str):
    """
    対象の音声エンジンにリクエストを投げて再生する。
    MVPではスタブとして機能し、標準出力にログを残す。
    """
    print(f"[VOICE ROUTER] Mode: {mode} | Text: {text}")

    if mode == "NURSE":
        # ナースロボタイプT (ローカル等) に投げる想定
        # 例: requests.post("http://localhost:50031/audio_query", params={"text": text...})
        pass
    elif mode == "OAI":
        # OpenAI TTS APIに投げる想定
        pass
    elif mode == "HYB":
        # 長文はOAI、短文や感情表現はNURSEといったハイブリッド処理の想定
        pass

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "voice-router"}

@app.post("/speak")
def speak_command(req: SpeakRequest, bg_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Coreから呼び出される発話エンドポイント"""
    mode = req.override_mode or get_current_voice_mode(db)
    # バックグラウンドで非同期に発話処理を走らせる
    bg_tasks.add_task(generate_and_play_audio, req.text, mode)
    return {"status": "accepted", "mode_used": mode, "text": req.text}

@app.get("/current_mode")
def current_mode(db: Session = Depends(get_db)):
    mode = get_current_voice_mode(db)
    return {"voice_mode": mode}
