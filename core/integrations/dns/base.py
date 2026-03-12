import logging
import httpx
import asyncio
from typing import Dict, Any, Optional

logger = logging.getLogger("core.dns")

class DNSClientBase:
    """DNS統合クライアントの基底クラス"""
    def __init__(self, base_url: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                logger.error(f"HTTP GET failed for {url}: {e}")
                return {"error": str(e), "url": url}

    async def _post(self, endpoint: str, json_data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(url, json=json_data, headers=headers)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                logger.error(f"HTTP POST failed for {url}: {e}")
                return {"error": str(e), "url": url}
