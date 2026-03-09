import os
import sys
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = FastAPI(title="shipOS GUI Dashboard")

html_template = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>shipOS Dashboard - AYN</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: 'Noto Sans JP', 'Hiragino Sans', 'Meiryo', monospace;
            background: linear-gradient(135deg, #0b1a2e 0%, #1a0a2e 100%);
            color: #e0e0e0;
            margin: 0;
            padding: 20px;
            min-height: 100vh;
        }
        h1 {
            color: #f0f0f0;
            border-bottom: 2px solid #4af626;
            padding-bottom: 10px;
            font-size: 1.5em;
        }
        h2 { color: #4af626; margin-top: 0; font-size: 1.1em; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px; }
        @media (max-width: 768px) { .grid { grid-template-columns: 1fr; } }
        .card {
            background: rgba(17, 41, 72, 0.8);
            padding: 15px;
            border-radius: 10px;
            border: 1px solid rgba(74, 246, 38, 0.2);
            backdrop-filter: blur(10px);
        }
        .card-full { grid-column: 1 / -1; }
        .status-row { display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
        .status-key { color: #00bcd4; font-weight: bold; font-size: 0.85em; }
        .status-val { color: #fff; font-size: 0.85em; word-break: break-all; max-width: 60%; text-align: right; }
        .alert { color: #f44336; font-weight: bold; }
        .warning { color: #ffeb3b; font-weight: bold; }
        
        /* ログビューア */
        .log-container {
            max-height: 500px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 0.8em;
            line-height: 1.6;
        }
        .log-entry {
            padding: 3px 8px;
            border-bottom: 1px solid rgba(255,255,255,0.03);
        }
        .log-entry:hover { background: rgba(255,255,255,0.05); }
        .log-time { color: #888; margin-right: 8px; }
        .log-service { color: #00bcd4; margin-right: 8px; font-weight: bold; }
        .log-INFO { color: #4af626; }
        .log-WARN { color: #ffeb3b; }
        .log-ERROR { color: #f44336; }
        .log-CRITICAL { color: #ff1744; font-weight: bold; }
        .log-msg { color: #e0e0e0; }
        
        .filter-bar {
            display: flex; gap: 8px; margin-bottom: 10px; flex-wrap: wrap;
        }
        .filter-btn {
            padding: 4px 12px;
            border: 1px solid rgba(74, 246, 38, 0.3);
            background: transparent;
            color: #4af626;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.8em;
        }
        .filter-btn:hover, .filter-btn.active {
            background: rgba(74, 246, 38, 0.2);
        }
        .refresh-info { color: #666; font-size: 0.75em; text-align: right; margin-top: 5px; }
    </style>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap" rel="stylesheet">
</head>
<body>
    <h1>⚓ shipOS DASHBOARD — AYN</h1>
    
    <div class="grid">
        <div class="card">
            <h2>🚢 System Status</h2>
            {% for item in system_states %}
            <div class="status-row">
                <span class="status-key">{{ item.key }}</span>
                <span class="status-val">{{ item.value }}</span>
            </div>
            {% endfor %}
        </div>
        
        <div class="card">
            <h2>💰 Billing Status</h2>
            <div class="status-row">
                <span class="status-key">Mode</span>
                <span class="status-val">{{ billing_data.is_special_day and "Special Day" or "Normal Day" }}</span>
            </div>
            <div class="status-row">
                <span class="status-key">Cost (JPY)</span>
                <span class="status-val">{{ billing_data.current_cost_jpy }} 円</span>
            </div>
            <div class="status-row">
                <span class="status-key">Alert Level</span>
                <span class="status-val {% if billing_data.alert_level == 'STOP' %}alert{% elif billing_data.alert_level in ['ALERT', 'WARNING'] %}warning{% endif %}">
                    {{ billing_data.alert_level }}
                </span>
            </div>
        </div>
        
        <div class="card card-full">
            <h2>📋 システムログ（最新100件）</h2>
            <div class="filter-bar">
                <button class="filter-btn active" onclick="filterLogs('ALL')">ALL</button>
                <button class="filter-btn" onclick="filterLogs('INFO')">INFO</button>
                <button class="filter-btn" onclick="filterLogs('WARN')">WARN</button>
                <button class="filter-btn" onclick="filterLogs('ERROR')">ERROR</button>
                <button class="filter-btn" onclick="filterLogs('CRITICAL')">CRITICAL</button>
            </div>
            <div class="log-container" id="log-container">
                {% for log in logs %}
                <div class="log-entry" data-level="{{ log.level }}">
                    <span class="log-time">{{ log.time }}</span>
                    <span class="log-service">[{{ log.service }}]</span>
                    <span class="log-{{ log.level }}">{{ log.level }}</span>
                    <span class="log-msg">{{ log.message }}</span>
                </div>
                {% endfor %}
                {% if not logs %}
                <div class="log-entry"><span class="log-msg">ログがまだないよ。</span></div>
                {% endif %}
            </div>
            <div class="refresh-info">30秒ごとに自動更新</div>
        </div>
    </div>
    
    <script>
        // ログフィルタリング
        function filterLogs(level) {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
            document.querySelectorAll('.log-entry').forEach(entry => {
                if (level === 'ALL' || entry.dataset.level === level) {
                    entry.style.display = '';
                } else {
                    entry.style.display = 'none';
                }
            });
        }
        // 30秒ごとに自動更新
        setTimeout(function(){ window.location.reload(); }, 30000);
    </script>
</body>
</html>
"""

import tempfile
import jinja2

template_dir = tempfile.mkdtemp()
with open(os.path.join(template_dir, "index.html"), "w", encoding="utf-8") as f:
    f.write(html_template)

from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader(template_dir))
template = env.get_template("index.html")

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
    logs = []

    # DB からシステム状態とログを取得
    try:
        from shared.database import SessionLocal
        from shared.models import SystemState, SystemLog
        db = SessionLocal()
        
        # System states
        states = db.query(SystemState).all()
        system_states = [{"key": s.key, "value": s.value} for s in states]
        
        # System logs (最新100件、新しい順)
        log_entries = db.query(SystemLog).order_by(SystemLog.created_at.desc()).limit(100).all()
        for entry in log_entries:
            created = entry.created_at
            time_str = created.strftime("%m/%d %H:%M:%S") if created else "??"
            logs.append({
                "time": time_str,
                "service": entry.service_name or "??",
                "level": entry.level or "INFO",
                "message": entry.message or ""
            })
        
        db.close()
    except Exception as e:
        print(f"DB access error: {e}")
        import traceback
        traceback.print_exc()

    # Billing data
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://billing-guard:8002/status", timeout=2.0)
            if resp.status_code == 200:
                billing_data = resp.json()
    except Exception as e:
        print(f"Billing access error: {e}")

    rendered = template.render(
        request=request,
        system_states=system_states,
        billing_data=billing_data,
        logs=logs
    )
    return HTMLResponse(content=rendered)
