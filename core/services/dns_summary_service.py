from sqlalchemy.orm import Session
from sqlalchemy import func
from shared.models import DNSMetrics
from datetime import datetime, timedelta, timezone
from shared.bilingual_formatter import format_bilingual

class DNSSummaryService:
    """DNSメトリクスの集計と要約を行うサービス"""
    
    @staticmethod
    def get_daily_stats(db: Session):
        """今日の最新/累計統計を取得"""
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # 各サービスの最新レコードを取得
        services = ["adguard", "pihole", "unbound"]
        results = {}
        
        for s in services:
            latest = db.query(DNSMetrics).filter(
                DNSMetrics.service_type == s,
                DNSMetrics.created_at >= today_start
            ).order_by(DNSMetrics.created_at.desc()).first()
            
            if latest:
                results[s] = {
                    "status": latest.status,
                    "query_count": latest.query_count,
                    "block_count": latest.block_count,
                    "latency": latest.latency_ms
                }
            else:
                results[s] = {"status": "OFFLINE", "query_count": 0, "block_count": 0}
                
        return results

    @staticmethod
    def format_status_report(stats: dict) -> str:
        """博多弁でのDNSステータスレポート作成"""
        ag = stats.get("adguard", {})
        ph = stats.get("pihole", {})
        ub = stats.get("unbound", {})
        
        ja = (f"DNS基盤の状況ば報告するね、マスター！🚩\n\n"
              f"・AdGuard Home: {ag['status']} (ブロック: {ag['block_count']}件)\n"
              f"・Pi-hole: {ph['status']} (ブロック: {ph['block_count']}件)\n"
              f"・Unbound: {ub['status']}" + (f" (応答: {ub['latency']:.1f}ms)" if ub.get('latency') else "") + "\n\n"
              f"今日も安全なネット航海ばい！✨")
              
        en = (f"Reporting DNS infrastructure status, Master! 🚩\n\n"
              f"- AdGuard Home: {ag['status']} (Blocked: {ag['block_count']})\n"
              f"- Pi-hole: {ph['status']} (Blocked: {ph['block_count']})\n"
              f"- Unbound: {ub['status']}" + (f" (Latency: {ub['latency']:.1f}ms)" if ub.get('latency') else "") + "\n\n"
              f"Safe sailing today! ✨")
              
        return format_bilingual(ja, en)
