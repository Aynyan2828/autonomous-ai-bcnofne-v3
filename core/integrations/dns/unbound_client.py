import socket
import time
import asyncio
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger("core.dns")

class UnboundClient:
    """Unbound 監視クライアント"""
    def __init__(self, host: str = "127.0.0.1", port: int = 53, timeout: float = 2.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    async def check_health(self) -> Dict[str, Any]:
        """UDP 53番ポートへの実クエリによる疎通確認"""
        # クエリの全体タイムアウトは timeout 秒
        start_time = time.time()
        
        # 1. まずは実際の DNS クエリ (google.com A)
        try:
            query = (
                b'\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00'
                b'\x06google\x03com\x00\x00\x01\x00\x01'
            )
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.timeout)
            sock.sendto(query, (self.host, self.port))
            data, _ = sock.recvfrom(512)
            sock.close()
            
            if len(data) > 0:
                latency = (time.time() - start_time) * 1000
                return {"status": "ONLINE", "latency_ms": latency, "check_method": "DNS-Query"}
        except socket.timeout:
            # タイムアウトした場合は 2000ms+ の遅延として報告
            return {
                "status": "OFFLINE (TIMEOUT)", 
                "latency_ms": (time.time() - start_time) * 1000,
                "error": f"Query timed out after {self.timeout}s. Check Unbound Port 5335 exposure or ACL."
            }
        except Exception as e:
            # 接続拒否などの場合
            return {"status": "OFFLINE", "error": str(e)}

    async def get_metrics(self) -> Dict[str, Any]:
        return await self.check_health()
