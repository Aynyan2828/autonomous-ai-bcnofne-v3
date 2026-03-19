import os
import sys

# パス追加
sys.path.append(os.path.abspath('.'))

from shared.database import SessionLocal
from shared.models import SystemState

def check_billing():
    db = SessionLocal()
    try:
        keys = [
            "billing_cost_jpy", 
            "billing_total_cost_jpy", 
            "billing_requests", 
            "billing_date", 
            "billing_alert_level",
            "ai_status",
            "ai_stop_reason",
            "install_date"
        ]
        print("--- Current Billing State ---")
        for key in keys:
            s = db.query(SystemState).filter_by(key=key).first()
            val = s.value if s else "N/A"
            print(f"{key}: {val}")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_billing()
