from .base import DNSClientBase, logger
from typing import Dict, Any, Optional

class PiholeClient(DNSClientBase):
    """Pi-hole API クライアント"""
    def __init__(self, base_url: str, api_token: str, timeout: float = 5.0):
        # Pi-hole API usually requires ?auth=TOKEN or &auth=TOKEN
        super().__init__(base_url, timeout)
        self.api_token = api_token

    async def get_summary(self) -> Optional[Dict[str, Any]]:
        """概要情報の取得 (summaryRaw)"""
        params = {"summaryRaw": 1}
        if self.api_token:
            params["auth"] = self.api_token
        
        # もし base_url にすでに /admin が含まれていたら二重にならないようにする
        endpoint = "api.php" if self.base_url.endswith("/admin") else "admin/api.php"
        return await self._get(endpoint, params=params)

    async def get_top_items(self) -> Optional[Dict[str, Any]]:
        """上位クエリ/ドメインの取得"""
        params = {"topItems": 10}
        if self.api_token:
            params["auth"] = self.api_token
        endpoint = "api.php" if self.base_url.endswith("/admin") else "admin/api.php"
        return await self._get(endpoint, params=params)

    async def get_status(self) -> Optional[Dict[str, Any]]:
        """稼働状態の取得"""
        params = {"status": 1}
        if self.api_token:
            params["auth"] = self.api_token
        endpoint = "api.php" if self.base_url.endswith("/admin") else "admin/api.php"
        return await self._get(endpoint, params=params)
