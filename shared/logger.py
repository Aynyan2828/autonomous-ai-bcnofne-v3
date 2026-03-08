import httpx
import asyncio
import os
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from shared.database import SessionLocal
from shared.models import SystemLog, LogLevel

class ShipLogger:
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.discord_url = "http://discord-gateway:8006/notify"

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

    async def _notify_discord(self, level: str, message: str):
        # Only notify Discord for WARN, ERROR, CRITICAL
        if level not in [LogLevel.WARN.value, LogLevel.ERROR.value, LogLevel.CRITICAL.value]:
            return
            
        async with httpx.AsyncClient() as client:
            try:
                payload = {
                    "message": f"[{self.service_name}] **{level}**: {message}",
                    "username": f"shipOS {self.service_name.upper()}"
                }
                await client.post(self.discord_url, json=payload, timeout=2.0)
            except Exception as e:
                print(f"[LOGGER ERROR] Discord Fail: {e}")

    def info(self, message: str):
        print(f"[{self.service_name}] INFO: {message}")
        self._log_to_db(LogLevel.INFO.value, message)

    def warn(self, message: str):
        print(f"[{self.service_name}] WARN: {message}")
        self._log_to_db(LogLevel.WARN.value, message)
        asyncio.create_task(self._notify_discord(LogLevel.WARN.value, message))

    def error(self, message: str):
        print(f"[{self.service_name}] ERROR: {message}")
        self._log_to_db(LogLevel.ERROR.value, message)
        asyncio.create_task(self._notify_discord(LogLevel.ERROR.value, message))

    def critical(self, message: str):
        print(f"[{self.service_name}] CRITICAL: {message}")
        self._log_to_db(LogLevel.CRITICAL.value, message)
        asyncio.create_task(self._notify_discord(LogLevel.CRITICAL.value, message))

# Usage: logger = ShipLogger("core")
