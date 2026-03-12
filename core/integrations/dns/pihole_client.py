from .base import DNSClientBase, logger
from typing import Dict, Any, Optional
import httpx

class PiholeClient(DNSClientBase):
    """Pi-hole API クライアント (v5 api.php 対応)"""
    def __init__(self, base_url: str, api_token: Optional[str] = None, timeout: float = 5.0):
        super().__init__(base_url, timeout)
        self.api_token = api_token

    async def get_summary(self) -> Optional[Dict[str, Any]]:
        """概要情報の取得 (summaryRaw)"""
        params = {"summaryRaw": 1}
        if self.api_token:
            params["auth"] = self.api_token
        
        # 400エラー対策: /admin があっても重複させず、様々なパスを試す
        # もし base_url に /admin が含まれていたら削除して正規化
        base = self.base_url.replace("/admin", "").rstrip("/")
        
        # まず admin/api.php を試す
        url = f"{base}/admin/api.php"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    return resp.json()
                # 失敗したらルートの api.php を試す
                url = f"{base}/api.php"
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    return resp.json()
                return {"error": f"Status {resp.status_code}", "url": url}
            except Exception as e:
                return {"error": str(e), "url": url}

    async def get_status(self) -> Optional[Dict[str, Any]]:
        """稼働状態の取得"""
        params = {"status": 1}
        if self.api_token:
            params["auth"] = self.api_token
        
        base = self.base_url.replace("/admin", "").rstrip("/")
        url = f"{base}/admin/api.php"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    return resp.json()
                return {"error": f"Status {resp.status_code}", "url": url}
            except Exception as e:
                return {"error": str(e), "url": url}
