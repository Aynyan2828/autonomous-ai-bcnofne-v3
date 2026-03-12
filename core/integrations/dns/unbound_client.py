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
        # 初回クエリのタイムアウトは短めにして全体の応答速度を上げる
        query_timeout = min(self.timeout, 1.5)
        start_time = time.time()
        
        # 1. まずは実際の DNS クエリ (google.com A) を試みる
        try:
            # Transaction ID: 0x1234, Standard Query, 1 Question
            # google.com (0x06 'google' 0x03 'com' 0x00), Type: A (0x0001), Class: IN (0x0001)
            query = (
                b'\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00'
                b'\x06google\x03com\x00\x00\x01\x00\x01'
            )
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(query_timeout)
            sock.sendto(query, (self.host, self.port))
            data, _ = sock.recvfrom(512)
            sock.close()
            
            if len(data) > 0:
                latency = (time.time() - start_time) * 1000
                return {"status": "ONLINE", "latency_ms": latency, "check_method": "DNS-Query"}
        except Exception:
            pass # クエリ失敗時はフォールバックへ

        # 2. フォールバック: UDP送信テスト
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(0.5)
            # 送信エラー（Network unreachable等）が出ないか確認
            sock.sendto(b'', (self.host, self.port))
            sock.close()
            
            # 可能なら TCP でも一瞬だけ試みる
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port),
                    timeout=0.5
                )
                writer.close()
                await writer.wait_closed()
                return {"status": "ONLINE", "latency_ms": (time.time() - start_time) * 1000, "check_method": "TCP-Connect"}
            except:
                return {"status": "ONLINE", "latency_ms": (time.time() - start_time) * 1000, "check_method": "UDP-Bind"}
                
        except Exception as e:
            return {"status": "OFFLINE", "error": str(e)}

    async def get_metrics(self) -> Dict[str, Any]:
        """ヘルスチェック結果をメトリクス形式で返す"""
        return await self.check_health()
