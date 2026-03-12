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
        """UDP 53番ポートへの実クエリによる疎通確認"""
        start_time = time.time()
        try:
            # 最小限の DNS クエリパケット (localhost の A レコード)
            # Transaction ID: 0x1234
            # Flags: 0x0100 (Standard query)
            # Questions: 1, Answer RRs: 0, Authority RRs: 0, Additional RRs: 0
            # Query: localhost (0x09 'localhost' 0x00), Type: A (0x0001), Class: IN (0x0001)
            query = (
                b'\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00'
                b'\x09localhost\x00\x00\x01\x00\x01'
            )
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.timeout)
            
            sock.sendto(query, (self.host, self.port))
            data, _ = sock.recvfrom(512) # 応答を待機
            sock.close()
            
            if len(data) > 0:
                latency = (time.time() - start_time) * 1000
                return {
                    "status": "ONLINE",
                    "latency_ms": latency
                }
            else:
                return {"status": "OFFLINE", "error": "Empty response"}
                
        except socket.timeout:
            return {"status": "OFFLINE", "error": "Timeout"}
        except Exception as e:
            logger.error(f"Unbound UDP query failed on {self.host}:{self.port}: {e}")
            return {
                "status": "OFFLINE",
                "error": str(e)
            }
            
    async def get_metrics(self) -> Dict[str, Any]:
        """ヘルスチェック結果をメトリクス形式で返す"""
        return await self.check_health()
