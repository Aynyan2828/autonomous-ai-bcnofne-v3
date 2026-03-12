from .base import DNSClientBase, logger
from typing import Dict, Any, Optional
import httpx

class PiholeClient(DNSClientBase):
    """Pi-hole API クライアント (v5 api.php 対応)"""
    def __init__(self, base_url: str, api_token: Optional[str] = None, timeout: float = 5.0):
        # ユーザーが末尾に /admin を入れても正規化
        base = base_url.strip().replace("/admin", "").rstrip("/")
        super().__init__(base, timeout)
        self.api_token = api_token.strip() if api_token else None

    async def get_summary(self) -> Any:
        params: Dict[str, Any] = {"summaryRaw": 1}
        return await self._try_api(params)

    async def get_status(self) -> Any:
        params: Dict[str, Any] = {"status": 1}
        return await self._try_api(params)

    async def _try_api(self, params: Dict[str, Any]) -> Any:
        """複数のエンドポイントを試行し、400エラー等に柔軟に対応"""
        if self.api_token:
            params["auth"] = self.api_token
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # 1. まずは admin/api.php
            url = f"{self.base_url}/admin/api.php"
            try:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and not data:
                        pass # Continue to next or fallback
                    else:
                        return data
                elif resp.status_code == 400:
                    # 400 の理由をより長くキャプチャ
                    text = resp.text[:200]
                    logger.warning(f"Pi-hole 400 Error: {text}")
                    if "auth" in params:
                        # トークンなしで試す（一部の統計はトークン不要な場合があるため）
                        p2 = params.copy()
                        p2.pop("auth")
                        resp2 = await client.get(url, params=p2)
                        if resp2.status_code == 200:
                            return resp2.json()
                    return {"error": f"Bad Request (400): {text}"}
            except Exception:
                pass

            # 2. 失敗したらルートの api.php
            url = f"{self.base_url}/api.php"
            try:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                return {"error": str(e), "url": url}
            
            return {"error": "Pi-hole API failed (check URL or Token format)"}
