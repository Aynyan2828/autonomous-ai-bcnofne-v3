from .base import DNSClientBase, logger
from typing import Dict, Any, Optional
import base64
import httpx

class AdGuardClient(DNSClientBase):
    """AdGuard Home REST API クライアント (全角パスワード対応版)"""
    def __init__(self, base_url: str, username: str, password: str, timeout: float = 5.0):
        super().__init__(base_url.strip().rstrip("/"), timeout)
        # AdGuard Home のデフォルトユーザー名は admin であることが多い
        u = username.strip() if username.strip() else "admin"
        p = password.strip()
        auth_bytes = f"{u}:{p}".encode("utf-8")
        auth_b64 = base64.b64encode(auth_bytes).decode("ascii")
        self.headers = {"Authorization": f"Basic {auth_b64}"}

    async def _get_with_auth(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url, params=params, headers=self.headers)
                if resp.status_code == 200:
                    return resp.json()
                
                # 401 の場合は認証方法やユーザー名の不一致を疑う
                if resp.status_code == 401:
                    return {
                        "error": "HTTP 401 Unauthorized",
                        "body": "User/Pass mismatch or AdGuard 'auth_name' config error.",
                        "url": url
                    }
                
                body_peek = resp.text[:200]
                return {
                    "error": f"HTTP {resp.status_code}",
                    "body": body_peek,
                    "url": url
                }
            except Exception as e:
                logger.error(f"AdGuard GET failed for {url}: {e}")
                return {"error": str(e), "url": url}

    async def get_stats(self) -> Any:
        return await self._get_with_auth("control/stats")

    async def get_status(self) -> Any:
        return await self._get_with_auth("control/status")

    async def get_history(self, limit: int = 10) -> Any:
        return await self._get_with_auth("control/query_log", params={"limit": limit})
    
    async def get_filtering_config(self) -> Any:
        return await self._get_with_auth("control/filtering/status")
