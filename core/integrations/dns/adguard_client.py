from .base import DNSClientBase, logger
from typing import Dict, Any, Optional
import base64
import httpx

class AdGuardClient(DNSClientBase):
    """AdGuard Home REST API クライアント"""
    def __init__(self, base_url: str, username: str, password: str, timeout: float = 5.0):
        super().__init__(base_url.strip().rstrip("/"), timeout)
        self.auth = httpx.BasicAuth(username.strip(), password.strip())

    async def _get_with_auth(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        async with httpx.AsyncClient(timeout=self.timeout, auth=self.auth) as client:
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                logger.error(f"AdGuard GET failed for {url}: {e}")
                return {"error": str(e), "url": url}

    async def get_stats(self) -> Any:
        return await self._get_with_auth("control/stats")

    async def get_status(self) -> Any:
        return await self._get_with_auth("control/status")

    async def get_history(self, limit: int = 10) -> Any:
        """クエリ履歴の取得"""
        return await self._get_with_auth("control/query_log", params={"limit": limit})
    
    async def get_filtering_config(self) -> Any:
        """フィルタリング設定の取得"""
        return await self._get_with_auth("control/filtering/status")
