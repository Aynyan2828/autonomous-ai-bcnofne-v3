from .base import DNSClientBase, logger
from typing import Dict, Any, Optional
import httpx

class PiholeClient(DNSClientBase):
    """Pi-hole API クライアント (v5 api.php 対応)"""
    def __init__(self, base_url: str, api_token: Optional[str] = None, timeout: float = 5.0):
        super().__init__(base_url, timeout)
        self.api_token = api_token.strip() if api_token else None

    async def get_summary(self) -> Optional[Dict[str, Any]]:
        """概要情報の取得 (summaryRaw)"""
        # auth が必要な場合が多い
        params = {"summaryRaw": 1}
        if self.api_token:
            params["auth"] = self.api_token
        
        base = self.base_url.replace("/admin", "").rstrip("/")
        
        # 400 Bad Request を避けるため、まず標準的なパスを試行
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for endpoint in ["/admin/api.php", "/api.php"]:
                url = f"{base}{endpoint}"
                try:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        try:
                            data = resp.json()
                            if isinstance(data, list) and not data:
                                # 空のリストが返ってくる場合は auth 失敗の可能性が高い
                                continue
                            return data
                        except Exception:
                            continue
                    elif resp.status_code == 400:
                        # 400 の場合はパラメータが気に入らない可能性あり。auth なしで試してみる
                        if "auth" in params:
                            p_no_auth = {"summaryRaw": 1}
                            resp2 = await client.get(url, params=p_no_auth)
                            if resp2.status_code == 200:
                                return resp2.json()
                except Exception as e:
                    logger.debug(f"Pi-hole check failed for {url}: {e}")
            
            return {"error": "All Pi-hole endpoints failed or returned 400"}

    async def get_status(self) -> Optional[Dict[str, Any]]:
        """稼働状態の取得"""
        params = {"status": 1}
        if self.api_token:
            params["auth"] = self.api_token
        
        base = self.base_url.replace("/admin", "").rstrip("/")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            url = f"{base}/admin/api.php"
            try:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    return resp.json()
                return {"error": f"Status {resp.status_code}"}
            except Exception as e:
                return {"error": str(e)}
