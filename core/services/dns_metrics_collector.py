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
        self.adguard = AdGuardClient(
            os.getenv("ADGUARD_URL", "http://localhost:8080"),
            os.getenv("ADGUARD_USERNAME", "admin"),
            os.getenv("ADGUARD_PASSWORD", "password")
        )
        self.pihole = PiholeClient(
            os.getenv("PIHOLE_URL", "http://localhost/admin"),
            os.getenv("PIHOLE_API_TOKEN", "")
        )
        self.unbound = UnboundClient(
            os.getenv("UNBOUND_HOST", "127.0.0.1"),
            int(os.getenv("UNBOUND_PORT", "53"))
        )

    async def collect_all(self):
        """全サービスのメトリクスを収集してDBに保存"""
        db = SessionLocal()
        try:
            await asyncio.gather(
                self._collect_adguard(db),
                self._collect_pihole(db),
                self._collect_unbound(db)
            )
        finally:
            db.close()

    async def _collect_adguard(self, db: Session):
        stats = await self.adguard.get_stats()
        status_info = await self.adguard.get_status()
        
        status = "ONLINE" if status_info else "OFFLINE"
        metrics = DNSMetrics(
            service_type="adguard",
            status=status,
            query_count=stats.get("num_dns_queries", 0) if stats else 0,
            block_count=stats.get("num_blocked_filtering", 0) if stats else 0,
            metrics_json=json.dumps(stats) if stats else None
        )
        db.add(metrics)
        db.commit()

    async def _collect_pihole(self, db: Session):
        summary = await self.pihole.get_summary()
        status_info = await self.pihole.get_status()
        
        status = "ONLINE" if (status_info and status_info.get("status") == "enabled") else "OFFLINE"
        metrics = DNSMetrics(
            service_type="pihole",
            status=status,
            query_count=summary.get("dns_queries_today", 0) if summary else 0,
            block_count=summary.get("ads_blocked_today", 0) if summary else 0,
            metrics_json=json.dumps(summary) if summary else None
        )
        db.add(metrics)
        db.commit()

    async def _collect_unbound(self, db: Session):
        res = await self.unbound.get_metrics()
        metrics = DNSMetrics(
            service_type="unbound",
            status=res.get("status", "UNKNOWN"),
            latency_ms=res.get("latency_ms"),
            metrics_json=json.dumps(res)
        )
        db.add(metrics)
        db.commit()
