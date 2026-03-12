from .base import DNSClientBase, logger
from typing import Dict, Any, Optional
import base64
import httpx

class AdGuardClient(DNSClientBase):
    """AdGuard Home REST API クライアント (セッション/Basic 両対応版)"""
    def __init__(self, base_url: str, username: str, password: str, timeout: float = 5.0):
        super().__init__(base_url.strip().rstrip("/"), timeout)
        self.username = username.strip() if username.strip() else "admin"
        self.password = password.strip()
        self._session_cookies: Optional[httpx.Cookies] = None
        
        # 初期 Basic Auth ヘッダ
        auth_bytes = f"{self.username}:{self.password}".encode("utf-8")
        auth_b64 = base64.b64encode(auth_bytes).decode("ascii")
        self.headers = {"Authorization": f"Basic {auth_b64}"}

    async def _login_session(self, client: httpx.AsyncClient) -> bool:
        """Cookie ベースのセッションログインを試みる"""
        try:
            url = f"{self.base_url}/control/login"
            resp = await client.post(url, json={"name": self.username, "password": self.password})
            if resp.status_code == 200:
                self._session_cookies = resp.cookies
                return True
        except Exception as e:
            logger.warning(f"AdGuard session login failed: {e}")
        return False

    async def _get_with_auth(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        async with httpx.AsyncClient(timeout=self.timeout, cookies=self._session_cookies) as client:
            try:
                # 1. まずは既存の方式（Basic または Cookie）で試行
                resp = await client.get(url, params=params, headers=self.headers)
                
                # 401 の場合はセッションログインを試して再試行
                if resp.status_code == 401:
                    if await self._login_session(client):
                        # セッションが取れたら Authorization ヘッダなしで再試行
                        resp = await client.get(url, params=params)
                
                if resp.status_code == 200:
                    return resp.json()
                
                # 401 や 403 でもサーバーが応答しているなら ONLINE (要認証) とみなす情報を付与
                status = "OFFLINE"
                if resp.status_code in [401, 403]:
                    status = "ONLINE (Auth Required)"
                elif resp.status_code < 500:
                    status = "ONLINE"

                return {
                    "error": f"HTTP {resp.status_code}",
                    "body": resp.text[:200],
                    "status_override": status,
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
