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

    async def _login(self, client: httpx.AsyncClient) -> bool:
        """SID を取得する (v6 認証)"""
        if not self.password:
            return False
        
        try:
            url = f"{self.base_url}/api/auth"
            resp = await client.post(url, json={"password": self.password})
            if resp.status_code == 200:
                data = resp.json()
                self._sid = data.get("session", {}).get("sid")
                return self._sid is not None
        except Exception as e:
            logger.error(f"Pi-hole v6 login failed: {e}")
        return False

    async def get_summary(self) -> Any:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # v6 認証
            if not self._sid:
                await self._login(client)
            
            url = f"{self.base_url}/api/stats/summary"
            params = {}
            if self._sid:
                params["sid"] = self._sid
            
            try:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    return resp.json()
                
                # 401/403 なら再ログイン
                if resp.status_code in [401, 403]:
                    if await self._login(client):
                        params["sid"] = self._sid
                        resp = await client.get(url, params=params)
                        if resp.status_code == 200:
                            return resp.json()
                
                return {"error": f"Pi-hole v6 summary failed: {resp.status_code}", "body": resp.text[:100]}
            except Exception as e:
                # v5 互換フォールバック (念のため)
                v5_url = f"{self.base_url}/admin/api.php?summaryRaw=1"
                try:
                    resp5 = await client.get(v5_url)
                    if resp5.status_code == 200:
                        return resp5.json()
                except:
                    pass
                return {"error": str(e), "url": url}

    async def get_status(self) -> Any:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            if not self._sid:
                await self._login(client)
            
            # v6 では /api/dns/blocking でステータス取得
            url = f"{self.base_url}/api/dns/blocking"
            params = {}
            if self._sid:
                params["sid"] = self._sid
                
            try:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    # v5 互換の形式に変換
                    return {"status": "enabled" if data.get("blocking", False) else "disabled"}
                
                # v5 互換フォールバック
                v5_url = f"{self.base_url}/admin/api.php?status=1"
                resp5 = await client.get(v5_url)
                if resp5.status_code == 200:
                    return resp5.json()
                    
                return {"error": f"Pi-hole v6 status failed: {resp.status_code}"}
            except Exception as e:
                # v5 互換フォールバック
                v5_url = f"{self.base_url}/admin/api.php?status=1"
                try:
                    resp5 = await client.get(v5_url)
                    if resp5.status_code == 200:
                        return resp5.json()
                except:
                    pass
                return {"error": str(e)}
