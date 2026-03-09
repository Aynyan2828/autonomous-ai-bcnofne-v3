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
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>shipOS - AYN</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Noto Sans JP', 'Hiragino Sans', sans-serif;
            background: #0a0e1a;
            color: #e0e0e0;
            padding: 12px;
            -webkit-text-size-adjust: 100%;
        }
        h1 {
            color: #fff;
            font-size: 1.2em;
            padding: 8px 0;
            border-bottom: 1px solid #4af626;
            margin-bottom: 12px;
        }
        h2 { color: #4af626; font-size: 0.95em; margin-bottom: 8px; }
        
        .card {
            background: rgba(20, 35, 60, 0.9);
            padding: 12px;
            border-radius: 8px;
            border: 1px solid rgba(74, 246, 38, 0.15);
            margin-bottom: 10px;
        }
        
        .status-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 5px 0;
            border-bottom: 1px solid rgba(255,255,255,0.04);
            font-size: 0.82em;
        }
        .status-key { color: #00bcd4; font-weight: bold; min-width: 100px; }
        .status-val { color: #fff; text-align: right; word-break: break-all; flex: 1; margin-left: 8px; }
        .alert { color: #f44336 !important; }
        .warning { color: #ffeb3b !important; }
        
        /* ログビューア - モバイル最適化 */
        .log-container {
            max-height: 60vh;
            overflow-y: auto;
            -webkit-overflow-scrolling: touch;
            font-size: 0.75em;
            line-height: 1.5;
        }
        .log-entry {
            padding: 4px 6px;
            border-bottom: 1px solid rgba(255,255,255,0.03);
        }
        .log-entry:hover, .log-entry:active { background: rgba(255,255,255,0.05); }
        .log-head {
            display: flex;
            gap: 6px;
            align-items: center;
            flex-wrap: wrap;
        }
        .log-time { color: #666; font-size: 0.85em; }
        .log-svc { color: #00bcd4; font-weight: bold; }
        .log-INFO { color: #4af626; }
        .log-WARN { color: #ffeb3b; }
        .log-ERROR { color: #f44336; }
        .log-CRITICAL { color: #ff1744; font-weight: bold; }
        .log-msg { color: #ccc; display: block; margin-top: 2px; word-break: break-word; }
        
        .filter-bar {
            display: flex;
            gap: 5px;
            margin-bottom: 8px;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }
        .filter-btn {
            padding: 5px 12px;
            border: 1px solid rgba(74, 246, 38, 0.3);
            background: transparent;
            color: #4af626;
            border-radius: 15px;
            cursor: pointer;
            font-size: 0.8em;
            white-space: nowrap;
            -webkit-tap-highlight-color: transparent;
        }
        .filter-btn:active, .filter-btn.active {
            background: rgba(74, 246, 38, 0.25);
        }
        
        .refresh-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 6px;
        }
        .refresh-info { color: #555; font-size: 0.7em; }
        .refresh-btn {
            padding: 4px 10px;
            border: 1px solid #4af626;
            background: transparent;
            color: #4af626;
            border-radius: 4px;
            font-size: 0.75em;
            cursor: pointer;
        }
    </style>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap" rel="stylesheet">
</head>
<body>
    <h1>⚓ shipOS — AYN</h1>
    
    <!-- システム状態 -->
    <div class="card">
        <h2>🚢 Status</h2>
        {% for item in system_states %}
        <div class="status-row">
            <span class="status-key">{{ item.key }}</span>
            <span class="status-val">{{ item.value }}</span>
        </div>
        {% endfor %}
    </div>
    
    <!-- 課金状態 -->
    <div class="card">
        <h2>💰 Billing</h2>
        <div class="status-row">
            <span class="status-key">Cost</span>
            <span class="status-val">{{ billing_data.current_cost_jpy }} 円</span>
        </div>
        <div class="status-row">
            <span class="status-key">Alert</span>
            <span class="status-val {% if billing_data.alert_level == 'STOP' %}alert{% elif billing_data.alert_level in ['ALERT', 'WARNING'] %}warning{% endif %}">
                {{ billing_data.alert_level }}
            </span>
        </div>
    </div>
    
    <!-- ログ -->
    <div class="card">
        <h2>📋 ログ</h2>
        <div class="filter-bar">
            <button class="filter-btn active" onclick="filterLogs('ALL',this)">ALL</button>
            <button class="filter-btn" onclick="filterLogs('INFO',this)">INFO</button>
            <button class="filter-btn" onclick="filterLogs('WARN',this)">WARN</button>
            <button class="filter-btn" onclick="filterLogs('ERROR',this)">ERROR</button>
            <button class="filter-btn" onclick="filterLogs('CRITICAL',this)">CRIT</button>
        </div>
        <div class="log-container" id="log-container">
            {% for log in logs %}
            <div class="log-entry" data-level="{{ log.level }}">
                <div class="log-head">
                    <span class="log-time">{{ log.time }}</span>
                    <span class="log-svc">{{ log.service }}</span>
                    <span class="log-{{ log.level }}">{{ log.level }}</span>
                </div>
                <span class="log-msg">{{ log.message }}</span>
            </div>
            {% endfor %}
            {% if not logs %}
            <div class="log-entry"><span class="log-msg">ログがまだないよ。</span></div>
            {% endif %}
        </div>
        <div class="refresh-bar">
            <span class="refresh-info">30秒で自動更新</span>
            <button class="refresh-btn" onclick="location.reload()">↻ 更新</button>
        </div>
    </div>
    
    <script>
        function filterLogs(level, btn) {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.log-entry').forEach(e => {
                e.style.display = (level === 'ALL' || e.dataset.level === level) ? '' : 'none';
            });
        }
        setTimeout(() => location.reload(), 30000);
    </script>
</body>
</html>
"""

import tempfile
from jinja2 import Environment, FileSystemLoader

template_dir = tempfile.mkdtemp()
with open(os.path.join(template_dir, "index.html"), "w", encoding="utf-8") as f:
    f.write(html_template)

env = Environment(loader=FileSystemLoader(template_dir))
template = env.get_template("index.html")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "gui"}

@app.get("/", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    system_states = []
    billing_data = {"is_special_day": False, "current_cost_jpy": 0.0, "alert_level": "UNKNOWN"}
    logs = []

    try:
        from shared.database import SessionLocal
        from shared.models import SystemState, SystemLog
        db = SessionLocal()
        
        states = db.query(SystemState).all()
        system_states = [{"key": s.key, "value": s.value} for s in states]
        
        log_entries = db.query(SystemLog).order_by(SystemLog.created_at.desc()).limit(100).all()
        for entry in log_entries:
            created = entry.created_at
            time_str = created.strftime("%m/%d %H:%M") if created else "??"
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
