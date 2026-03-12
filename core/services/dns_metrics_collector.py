import json
import os
import asyncio
from datetime import datetime, timezone
from shared import init_db
from shared.database import SessionLocal
from shared.models import DNSMetrics
from core.integrations.dns.adguard_client import AdGuardClient
from core.integrations.dns.pihole_client import PiholeClient
from core.integrations.dns.unbound_client import UnboundClient
from shared.logger import ShipLogger

logger = ShipLogger("core.dns_collector")

class DNSMetricsCollector:
    """DNSメトリクスの定期収集を担当するクラス"""
    def __init__(self):
        host_ip = os.getenv("HOST_IP", "127.0.0.1")
        
        self.adguard = AdGuardClient(
            os.getenv("ADGUARD_URL", f"http://{host_ip}:8080"),
            os.getenv("ADGUARD_USERNAME", "admin"),
            os.getenv("ADGUARD_PASSWORD", "password")
        )
        self.pihole = PiholeClient(
            os.getenv("PIHOLE_URL", f"http://{host_ip}/admin"),
            os.getenv("PIHOLE_API_TOKEN", "")
        )
        self.unbound = UnboundClient(
            os.getenv("UNBOUND_HOST", host_ip),
            int(os.getenv("UNBOUND_PORT", "53"))
        )

    async def collect_all(self):
        """全サービスのメトリクスを収集してDBに保存 (逐次実行でSQLiteの競合を回避)"""
        await self._collect_adguard()
        await self._collect_pihole()
        await self._collect_unbound()

    async def _collect_adguard(self):
        db = SessionLocal()
        try:
            stats = await self.adguard.get_stats()
            status_info = await self.adguard.get_status()
            
            # get_stats/get_status が辞書を返し、その中に "error" があれば失敗とみなす
            is_success = status_info and "error" not in status_info
            status = "ONLINE" if is_success else "OFFLINE"
            
            metrics = DNSMetrics(
                service_type="adguard",
                status=status,
                query_count=stats.get("num_dns_queries", 0) if (stats and "error" not in stats) else 0,
                block_count=stats.get("num_blocked_filtering", 0) if (stats and "error" not in stats) else 0,
                metrics_json=json.dumps({"stats": stats, "status": status_info})
            )
            db.add(metrics)
            db.commit()
        except Exception as e:
            logger.error(f"AdGuard collection failed: {e}")
        finally:
            db.close()

    async def _collect_pihole(self):
        db = SessionLocal()
        try:
            summary = await self.pihole.get_summary()
            status_info = await self.pihole.get_status()
            
            is_success = status_info and "error" not in status_info and status_info.get("status") == "enabled"
            status = "ONLINE" if is_success else "OFFLINE"
            
            metrics = DNSMetrics(
                service_type="pihole",
                status=status,
                query_count=summary.get("dns_queries_today", 0) if (summary and "error" not in summary) else 0,
                block_count=summary.get("ads_blocked_today", 0) if (summary and "error" not in summary) else 0,
                metrics_json=json.dumps({"summary": summary, "status": status_info})
            )
            db.add(metrics)
            db.commit()
        except Exception as e:
            logger.error(f"Pi-hole collection failed: {e}")
        finally:
            db.close()

    async def _collect_unbound(self):
        db = SessionLocal()
        try:
            res = await self.unbound.get_metrics()
            metrics = DNSMetrics(
                service_type="unbound",
                status=res.get("status", "UNKNOWN"),
                latency_ms=res.get("latency_ms"),
                metrics_json=json.dumps(res)
            )
            db.add(metrics)
            db.commit()
        except Exception as e:
            logger.error(f"Unbound collection failed: {e}")
        finally:
            db.close()
