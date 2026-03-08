import httpx
import asyncio
import os
import json
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from shared.database import SessionLocal
from shared.models import SystemLog, LogLevel

class ShipLogger:
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.discord_url = "http://discord-gateway:8006/notify"
        self.json_log_path = os.path.join(os.getenv("HDD_MOUNT_PATH", "/mnt/hdd"), "logs", "system_log.json")
        
        # ログディレクトリの作成
        os.makedirs(os.path.dirname(self.json_log_path), exist_ok=True)

    def _log_to_db(self, level: str, message: str):
        db = SessionLocal()
        try:
            log_entry = SystemLog(
                service_name=self.service_name,
                level=level,
                message=message
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            print(f"[LOGGER ERROR] DB Fail: {e}")
        finally:
            db.close()

    def _log_to_json(self, level: str, message: str):
        """日本語 JSON 形式でログをファイルに追記する"""
        try:
            log_data = {
                "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
                "service": self.service_name,
                "level": level,
                "message": message
            }
            #追記モードで開く
            with open(self.json_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_data, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[LOGGER ERROR] JSON Fail: {e}")

    async def _notify_discord(self, level: str, message: str):
        # Only notify Discord for WARN, ERROR, CRITICAL
        if level not in [LogLevel.WARN.value, LogLevel.ERROR.value, LogLevel.CRITICAL.value]:
            return
            
        async with httpx.AsyncClient() as client:
            try:
                payload = {
                    "message": f"[{self.service_name}] **{level}**: {message}",
                    "username": f"BCNOFNe {self.service_name.upper()}"
                }
                await client.post(self.discord_url, json=payload, timeout=2.0)
            except Exception as e:
                print(f"[LOGGER ERROR] Discord Fail: {e}")

    def _send_notification(self, level: str, message: str):
        """非同期ループの有無に応じて通知を送る処操"""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._notify_discord(level, message))
        except RuntimeError:
            # ループがない場合（同期スレッドなど）は同期的に実行を試みる（簡易版）処操
            # ここではエラーを避けるために独立したスレッドで実行するか、単に無視する
            pass 

    def info(self, message: str):
        print(f"[{self.service_name}] INFO: {message}")
        self._log_to_db(LogLevel.INFO.value, message)
        self._log_to_json(LogLevel.INFO.value, message)

    def warn(self, message: str):
        print(f"[{self.service_name}] WARN: {message}")
        self._log_to_db(LogLevel.WARN.value, message)
        self._log_to_json(LogLevel.WARN.value, message)
        self._send_notification(LogLevel.WARN.value, message)

    def error(self, message: str):
        print(f"[{self.service_name}] ERROR: {message}")
        self._log_to_db(LogLevel.ERROR.value, message)
        self._log_to_json(LogLevel.ERROR.value, message)
        self._send_notification(LogLevel.ERROR.value, message)

    def critical(self, message: str):
        print(f"[{self.service_name}] CRITICAL: {message}")
        self._log_to_db(LogLevel.CRITICAL.value, message)
        self._log_to_json(LogLevel.CRITICAL.value, message)
        self._send_notification(LogLevel.CRITICAL.value, message)

# Usage: logger = ShipLogger("core")
