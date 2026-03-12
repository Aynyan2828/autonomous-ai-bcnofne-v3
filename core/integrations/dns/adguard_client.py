from .base import DNSClientBase, logger
from typing import Dict, Any, Optional
import base64

class AdGuardClient(DNSClientBase):
    """AdGuard Home REST API クライアント"""
    def __init__(self, base_url: str, username: str, password: str, timeout: float = 5.0):
        # 末尾の / を除くだけでなく、空白も削除
        super().__init__(base_url.strip().rstrip("/"), timeout)
        auth_str = f"{username.strip()}:{password.strip()}"
        self.headers = {
            "Authorization": f"Basic {base64.b64encode(auth_str.encode()).decode()}"
        }

    async def get_stats(self) -> Optional[Dict[str, Any]]:
        """統計情報の取得"""
        return await self._get("control/stats", headers=self.headers)

    async def get_status(self) -> Optional[Dict[str, Any]]:
        """現在のステータス/稼働情報の取得"""
        return await self._get("control/status", headers=self.headers)

    async def get_history(self, limit: int = 10) -> Optional[Dict[str, Any]]:
        """クエリ履歴の取得"""
        return await self._get("control/query_log", params={"limit": limit}, headers=self.headers)
    
    async def get_filtering_config(self) -> Optional[Dict[str, Any]]:
        """フィルタリング設定の取得"""
        return await self._get("control/filtering/status", headers=self.headers)
