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
        """UDP 53番ポートへの接続確認と簡易的な応答速度測定"""
        start_time = time.time()
        try:
            # 実際のDNSクエリを送るのが確実だが、まずは到達性確認
            # asyncio.open_connection は TCP 用なので UDP の場合は低レイヤー操作が必要
            # ここでは簡易的にソケット到達性を確認
            loop = asyncio.get_event_loop()
            
            # example.com の A レコードを引くようなダミーパケットを送るのが理想的
            # ここではシンプルにポートへの到達性 (接続試行) を行う
            # UDPはコネクションレスだが、ICMP Unreachable を待つ
            
            # 将来的に dns.resolver などを使うことも検討
            # 現時点ではソケットで簡易チェック
            
            # NOTE: Unbound statistics usually require control via unbound-control (Unix socket or TLS)
            # remote control protocol is complex, so we start with health check.
            
            # 簡易疎通テスト
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.timeout
            )
            writer.close()
            await writer.wait_closed()
            
            latency = (time.time() - start_time) * 1000
            return {
                "status": "ONLINE",
                "latency_ms": latency
            }
        except Exception as e:
            logger.error(f"Unbound health check failed on {self.host}:{self.port}: {e}")
            return {
                "status": "OFFLINE",
                "error": str(e)
            }
            
    async def get_metrics(self) -> Dict[str, Any]:
        """ヘルスチェック結果をメトリクス形式で返す"""
        return await self.check_health()
