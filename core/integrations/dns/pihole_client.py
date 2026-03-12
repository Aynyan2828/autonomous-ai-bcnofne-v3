from .base import DNSClientBase, logger
from typing import Dict, Any, Optional
import httpx

class PiholeClient(DNSClientBase):
    """Pi-hole API クライアント (v6 /api 対応)"""
    def __init__(self, base_url: str, password: Optional[str] = None, timeout: float = 5.0):
        # ユーザーが末尾に /admin を入れても正規化
        base = base_url.strip().replace("/admin", "").rstrip("/")
        super().__init__(base, timeout)
        self.password = password.strip() if password else None
        self._sid: Optional[str] = None
        self._last_error: Optional[str] = None

    async def _login(self, client: httpx.AsyncClient) -> bool:
        """SID を取得する (v6 認証)"""
        if not self.password:
            self._last_error = "Password not set in .env"
            return False
        
        try:
            url = f"{self.base_url}/api/auth"
            resp = await client.post(url, json={"password": self.password})
            if resp.status_code == 200:
                data = resp.json()
                self._sid = data.get("session", {}).get("sid")
                if self._sid:
                    self._last_error = None
                    return True
                else:
                    self._last_error = f"Login 200 but no SID in: {resp.text[:50]}"
            else:
                self._last_error = f"Login failed: HTTP {resp.status_code} - {resp.text[:100]}"
        except Exception as e:
            self._last_error = f"Login exception: {str(e)}"
            logger.error(f"Pi-hole v6 login failed: {e}")
        return False

    async def get_summary(self) -> Any:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            if not self._sid:
                if not await self._login(client):
                    return {"error": self._last_error}
            
            url = f"{self.base_url}/api/stats/summary"
            try:
                resp = await client.get(url, params={"sid": self._sid})
                if resp.status_code == 200:
                    return resp.json()
                
                # 401/403 なら再ログイン試行
                if resp.status_code in [401, 403]:
                    if await self._login(client):
                        resp = await client.get(url, params={"sid": self._sid})
                        if resp.status_code == 200:
                            return resp.json()
                
                return {"error": f"HTTP {resp.status_code}", "body": resp.text[:100]}
            except Exception as e:
                return {"error": str(e), "url": url}

    async def get_status(self) -> Any:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            if not self._sid:
                if not await self._login(client):
                    return {"error": self._last_error}
            
            url = f"{self.base_url}/api/dns/blocking"
            try:
                resp = await client.get(url, params={"sid": self._sid})
                if resp.status_code == 200:
                    data = resp.json()
                    return {"status": "enabled" if data.get("blocking", False) else "disabled"}
                
                if resp.status_code in [401, 403]:
                    if await self._login(client):
                        resp = await client.get(url, params={"sid": self._sid})
                        if resp.status_code == 200:
                            data = resp.json()
                            return {"status": "enabled" if data.get("blocking", False) else "disabled"}

                return {"error": f"HTTP {resp.status_code}", "body": resp.text[:100]}
            except Exception as e:
                return {"error": str(e)}
