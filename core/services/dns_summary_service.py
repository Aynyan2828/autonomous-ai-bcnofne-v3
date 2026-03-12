from sqlalchemy.orm import Session
from sqlalchemy import func
import json
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
                error_info = None
                if latest.metrics_json:
                    try:
                        m_data = json.loads(latest.metrics_json)
                        # 最上位またはサブキーにある "error" を探す
                        if isinstance(m_data, dict):
                            if "error" in m_data:
                                error_info = m_data["error"]
                            else:
                                for key in ["status", "summary", "stats"]:
                                    val = m_data.get(key)
                                    if isinstance(val, dict) and "error" in val:
                                        error_info = val["error"]
                                        break
                                    elif isinstance(val, str) and ("error" in val.lower() or "fail" in val.lower()):
                                        error_info = val
                                        break
                    except:
                        pass

                results[s] = {
                    "status": latest.status,
                    "query_count": latest.query_count,
                    "block_count": latest.block_count,
                    "latency": latest.latency_ms,
                    "last_checked": latest.created_at,
                    "error_info": error_info
                }
            else:
                results[s] = {"status": "OFFLINE", "query_count": 0, "block_count": 0, "last_checked": None, "error_info": None}
                
        return results

    @staticmethod
    def format_status_report(stats: dict) -> str:
        """博多弁でのDNSステータスレポート作成"""
        def format_service(name, data):
            status_emoji = "✅" if data['status'] == "ONLINE" else "❌"
            time_str = data['last_checked'].astimezone().strftime('%H:%M') if data['last_checked'] else "未取得"
            line = f"・{name}: {status_emoji} {data['status']} ({time_str})"
            
            if data['status'] == "ONLINE":
                if name == "Unbound":
                    line += f" 応答: {data.get('latency', 0):.1f}ms"
                else:
                    line += f" ブロック: {data['block_count']}件"
            elif data.get("error_info"):
                # エラーがある場合は短く表示
                err = data['error_info']
                if "ConnectError" in err or "Connection refused" in err:
                    line += " -> 接続失敗(Port/IPを確認)"
                else:
                    line += f" -> {err[:100]}"
            return line

        ag_line = format_service("AdGuard Home", stats.get("adguard", {}))
        ph_line = format_service("Pi-hole", stats.get("pihole", {}))
        ub_line = format_service("Unbound", stats.get("unbound", {}))

        ja = (f"DNS基盤の状況ば報告するね、マスター！🚩\n\n"
              f"{ag_line}\n"
              f"{ph_line}\n"
              f"{ub_line}\n\n"
              f"データは1日1回または手動でチェックしとるよ。今日も安全なネット航海ばい！✨")
              
        en = (f"Reporting DNS infrastructure status, Master! 🚩\n\n"
              f"Check results from around the system. Auto-updated daily or on-demand.\n\n"
              f"Safe sailing today! ✨")
              
        return format_bilingual(ja, en)
    @staticmethod
    def format_voyage_log(stats: dict) -> str:
        """今日のDNS航海ログ（統計要約）を作成"""
        # 各種数値の抽出
        ag = stats.get("adguard", {})
        ph = stats.get("pihole", {})
        ub = stats.get("unbound", {})

        ag_blocks = ag.get("block_count", 0)
        ph_queries = ph.get("query_count", 0)
        ph_blocks = ph.get("block_count", 0)
        ph_rate = (ph_blocks / ph_queries * 100) if ph_queries > 0 else 0
        ub_queries = ub.get("query_count", 0) # 現状は監視回数に近いが将来的に拡張可能

        ja = (f"DNS航海ログ報告🚢🚩\n\n"
              f"今日のDNSトラフィック状況たい！\n\n"
              f"🛡️ AdGuard Home\n"
              f"・ブロック件数: {ag_blocks}件\n\n"
              f"📊 Pi-hole\n"
              f"・総クエリ数: {ph_queries}件\n"
              f"・ブロック率: {ph_rate:.1f}%\n\n"
              f"🔗 Unbound\n"
              f"・再帰クエリ監視: {ub_queries}回成功\n\n"
              f"今日も安全なネット海域ば航海中たい！✨")

        en = (f"DNS Voyage Log Report 🚢🚩\n\n"
              f"Today's DNS traffic summary!\n\n"
              f"🛡️ AdGuard Home\n"
              f"- Blocked: {ag_blocks}\n\n"
              f"📊 Pi-hole\n"
              f"- Total Queries: {ph_queries}\n"
              f"- Block Rate: {ph_rate:.1f}%\n\n"
              f"🔗 Unbound\n"
              f"- Recursive Check: {ub_queries} successes\n\n"
              f"Sailing safely through the net today! ✨")

        return format_bilingual(ja, en)
