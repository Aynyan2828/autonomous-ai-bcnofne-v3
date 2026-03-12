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
                        # 各クライアントが返す error 情報を探す
                        for key in ["status", "summary", "stats"]:
                            val = m_data.get(key)
                            if isinstance(val, dict) and "error" in val:
                                error_info = val["error"]
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
                elif "401" in err or "403" in err:
                    line += " -> 認証失敗(User/Pass/Tokenを確認)"
                else:
                    line += f" -> {err[:30]}..."
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
