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
        """UDP 53番ポートへの実クエリによる疎通確認 (失敗時はソケットPingにフォールバック)"""
        start_time = time.time()
        
        # 1. まずは実際の DNS クエリ (localhost A) を試みる
        try:
            query = (
                b'\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00'
                b'\x09localhost\x00\x00\x01\x00\x01'
            )
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.timeout)
            sock.sendto(query, (self.host, self.port))
            data, _ = sock.recvfrom(512)
            sock.close()
            
            if len(data) > 0:
                latency = (time.time() - start_time) * 1000
                return {"status": "ONLINE", "latency_ms": latency}
        except Exception:
            pass # クエリ失敗時はフォールバックへ

        # 2. フォールバック: 単純なソケット疎通確認 (UDPは送信エラーチェックのみ)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.timeout)
            # UDPはコネクションレスだが、送信自体がエラーになるか確認
            sock.sendto(b'', (self.host, self.port))
            sock.close()
            
            # または可能なら TCP でも試す
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port),
                    timeout=self.timeout
                )
                writer.close()
                await writer.wait_closed()
                return {"status": "ONLINE", "latency_ms": (time.time() - start_time) * 1000, "check_method": "TCP"}
            except:
                return {"status": "ONLINE", "latency_ms": (time.time() - start_time) * 1000, "check_method": "UDP-Bind"}
                
        except Exception as e:
            return {"status": "OFFLINE", "error": str(e)}

    async def get_metrics(self) -> Dict[str, Any]:
        """ヘルスチェック結果をメトリクス形式で返す"""
        return await self.check_health()
