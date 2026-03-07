import os
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

app = FastAPI(title="shipOS GUI Dashboard")

# インラインでシンプルなテンプレートを持つ (MVP用)
html_template = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>shipOS Dashboard - AYN</title>
    <style>
        body { font-family: monospace; background-color: #0b1a2e; color: #4af626; margin: 0; padding: 20px; }
        h1 { color: #f0f0f0; border-bottom: 2px solid #4af626; padding-bottom: 10px; }
        .card { background-color: #112948; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        .status-key { font-weight: bold; color: #00bcd4; display: inline-block; width: 200px; }
        .status-val { color: #fff; }
        .alert { color: #f44336; font-weight: bold; }
        .warning { color: #ffeb3b; font-weight: bold; }
    </style>
</head>
<body>
    <h1>shipOS DASHBOARD ⚓ AYN</h1>
    <div class="card">
        <h2>System Status</h2>
        <div id="system-status">
            {% for item in system_states %}
                <div><span class="status-key">{{ item.key }}</span> <span class="status-val">{{ item.value }}</span></div>
            {% endfor %}
        </div>
    </div>
    <div class="card">
        <h2>Billing Status (Today)</h2>
        <div><span class="status-key">Mode:</span> <span class="status-val">{{ billing_data.is_special_day and "Special Day" or "Normal Day" }}</span></div>
        <div><span class="status-key">Cost (JPY):</span> <span class="status-val">{{ billing_data.current_cost_jpy }} 円</span></div>
        <div><span class="status-key">Alert Level:</span> 
             <span class="status-val {% if billing_data.alert_level == 'STOP' %}alert{% elif billing_data.alert_level in ['ALERT', 'WARNING'] %}warning{% endif %}">
                 {{ billing_data.alert_level }}
             </span>
        </div>
    </div>
    <script>
        setTimeout(function(){
           window.location.reload();
        }, 60000); // 1分おきに自動更新
    </script>
</body>
</html>
"""

# 簡易的にJinja2の設定をインラインで行う
import tempfile
import jinja2

template_dir = tempfile.mkdtemp()
with open(os.path.join(template_dir, "index.html"), "w", encoding="utf-8") as f:
    f.write(html_template)

templates = Jinja2Templates(directory=template_dir)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "gui"}

@app.get("/", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    """
    Core と Billing-Guard から情報を引っ張ってきて結合し、画面に表示する
    """
    system_states = []
    billing_data = {"is_special_day": False, "current_cost_jpy": 0.0, "alert_level": "UNKNOWN"}

    # direct DB access for states (since shared is mounted and available)
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from shared.database import SessionLocal
        from shared.models import SystemState
        db = SessionLocal()
        states = db.query(SystemState).all()
        system_states = [{"key": s.key, "value": s.value} for s in states]
        db.close()
    except Exception as e:
        print(f"DB access error: {e}")

    # fetch billing data via internal API
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://billing-guard:8002/status", timeout=2.0)
            if resp.status_code == 200:
                billing_data = resp.json()
    except Exception as e:
        print(f"Billing access error: {e}")

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "system_states": system_states, "billing_data": billing_data}
    )
