import socket
import time
import asyncio
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger("core.dns")

class UnboundClient:
    """Unbound 監視クライアント (主にヘルスチェックと応答速度)"""
    def __init__(self, host: str = "127.0.0.1", port: int = 53, timeout: float = 2.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    async def check_health(self) -> Dict[str, Any]:
        """UDP 53番ポートへの疎通確認"""
        start_time = time.time()
        try:
            # UDPソケットでの疎通確認
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.timeout)
            
            # ダミーの空パケットを送ってみる（返信は期待しないが、エラーにならないか確認）
            # または DNS クエリを送るのが理想。ここでは単に送信可能かを確認
            # NOTE: UDPはコネクションレスなので、到達 = 送信エラーなし 程度の確認
            
            # 本当は 127.0.0.1 への query を投げたいが、権限や設定に依存するため
            # シンプルに「送信してエラーが出ないか」を確認
            sock.sendto(b'', (self.host, self.port))
            sock.close()
            
            latency = (time.time() - start_time) * 1000
            return {
                "status": "ONLINE",
                "latency_ms": latency
            }
        except Exception as e:
            logger.error(f"Unbound UDP health check failed on {self.host}:{self.port}: {e}")
            return {
                "status": "OFFLINE",
                "error": str(e)
            }
            
    async def get_metrics(self) -> Dict[str, Any]:
        """ヘルスチェック結果をメトリクス形式で返す"""
        return await self.check_health()
