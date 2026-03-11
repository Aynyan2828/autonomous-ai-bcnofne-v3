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

        /* 提案ビュー & リッチDiff */
        .proposal-details {
            border: 1px solid rgba(74, 246, 38, 0.2);
            border-radius: 4px;
            margin-bottom: 8px;
            overflow: hidden;
        }
        .proposal-summary {
            background: rgba(255, 255, 255, 0.05);
            padding: 8px 10px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.85em;
            list-style: none;
        }
        .proposal-summary::-webkit-details-marker { display: none; }
        
        .prop-id { color: #00bcd4; font-family: monospace; }
        .prop-status { padding: 2px 6px; border-radius: 10px; font-size: 0.8em; font-weight: bold; }
        .status-PENDING { background: #ffeb3b; color: #000; }
        .status-APPROVED, .status-APPLIED { background: #4af626; color: #000; }
        .status-REJECTED, .status-FAILED { background: #f44336; color: #fff; }
        .prop-title { flex: 1; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: bold; }

        .prop-filter-bar {
            display: flex;
            gap: 4px;
            margin-bottom: 8px;
            overflow-x: auto;
            padding-bottom: 2px;
        }
        .prop-tab-btn {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #ccc;
            padding: 4px 10px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.8em;
            white-space: nowrap;
        }
        .prop-tab-btn:hover { background: rgba(255, 255, 255, 0.1); }
        .prop-tab-btn.active {
            background: rgba(0, 188, 212, 0.2);
            border-color: #00bcd4;
            color: #fff;
            font-weight: bold;
        }
        
        .proposal-content {
            padding: 10px;
            font-size: 0.8em;
            border-top: 1px solid rgba(255,255,255,0.05);
            background: rgba(0, 0, 0, 0.2);
        }
        .prop-desc { margin-bottom: 8px; color: #e0e0e0; line-height: 1.4; white-space: pre-wrap; }
        .prop-reason { margin-bottom: 8px; color: #00bcd4; font-style: italic; }
        
        .action-btn { padding: 6px 12px; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 0.9em; flex: 1; }
        .apply-btn { background: #4af626; color: #000; }
        .apply-btn:hover { background: #3dd320; }
        .reject-btn { background: #f44336; color: #fff; }
        .reject-btn:hover { background: #d32f2f; }
        
        /* Diff 表示スタイル */
        .diff-container { margin-top: 8px; }
        .diff-header { font-weight: bold; margin-bottom: 4px; color: #fff; display: flex; justify-content: space-between; align-items: center; }
        .full-code-btn { 
            background: #00bcd4; color: #000; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 0.9em; font-weight: bold; 
        }
        .diff-block {
            background: #111; padding: 8px; border-radius: 4px; overflow-x: auto; font-family: 'Courier New', monospace; font-size: 0.9em; line-height: 1.3;
        }
        .diff-line.add { color: #4af626; text-decoration: underline; background: rgba(74, 246, 38, 0.1); display: block; }
        .diff-line.del { color: #f44336; text-decoration: line-through; background: rgba(244, 67, 54, 0.1); display: block; }
        .diff-line.info { color: #00bcd4; opacity: 0.8; display: block; }
        
        /* 全文表示モーダル */
        #codeModal {
            display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0, 0, 0, 0.85); z-index: 1000; align-items: center; justify-content: center;
        }
        .modal-content {
            background: #1a1e29; width: 95%; height: 90%; border-radius: 8px; display: flex; flex-direction: column; overflow: hidden; border: 1px solid #00bcd4;
        }
        .modal-header {
            padding: 12px; background: #0a0e1a; border-bottom: 1px solid #00bcd4; display: flex; justify-content: space-between; align-items: center;
        }
        .modal-title { color: #00bcd4; font-size: 1.1em; font-weight: bold; word-break: break-all; }
        .modal-actions { display: flex; gap: 8px; }
        .copy-btn { color: #fff; background: #2196F3; border: none; padding: 4px 12px; border-radius: 4px; cursor: pointer; font-weight: bold; }
        .copy-btn:hover { background: #1976D2; }
        .close-btn { color: #fff; background: transparent; border: 1px solid #555; padding: 4px 12px; border-radius: 4px; cursor: pointer; }
        #fullCodeView {
            flex: 1; padding: 12px; overflow-y: auto; overflow-x: auto; background: #0d111b; color: #a5d6ff; font-family: monospace; font-size: 0.85em; white-space: pre-wrap;
        }

        /* 公開ログセクション */
        .public-log-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 10px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            cursor: pointer;
            font-size: 0.85em;
        }
        .public-log-item:hover { background: rgba(74, 246, 38, 0.1); }
        .log-cat { color: #4af626; font-weight: bold; font-size: 0.8em; border: 1px solid #4af626; padding: 1px 4px; border-radius: 4px; margin-right: 8px; }
        .log-name { flex: 1; color: #fff; }
        .log-date { color: #666; font-size: 0.8em; }
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
            <span class="status-key">Requests</span>
            <span class="status-val">{{ billing_data.request_count }} 回</span>
        </div>
        <div class="status-row">
            <span class="status-key">Alert</span>
            <span class="status-val {% if billing_data.alert_level == 'STOP' %}alert{% elif billing_data.alert_level in ['ALERT', 'WARNING'] %}warning{% endif %}">
                {{ billing_data.alert_level }}
            </span>
        </div>
    </div>
    
    <!-- 自律改修案 (Proposals) -->
    <div class="card">
        <h2>🛠️ 自律改修案 (Proposals)</h2>
        <div class="prop-filter-bar">
            <button class="prop-tab-btn active" onclick="filterProposals('PENDING', this)">PENDING</button>
            <button class="prop-tab-btn" onclick="filterProposals('APPLIED', this)">APPLIED</button>
            <button class="prop-tab-btn" onclick="filterProposals('REJECTED', this)">REJECTED</button>
            <button class="prop-tab-btn" onclick="filterProposals('FAILED', this)">FAILED</button>
            <button class="prop-tab-btn" onclick="filterProposals('ALL', this)">ALL</button>
        </div>
        
        {% for prop in proposals %}
        <details class="proposal-details prop-item" data-status="{{ prop.status }}">
            <summary class="proposal-summary">
                <span class="prop-id">{{ prop.id }}</span>
                <span class="prop-status status-{{ prop.status }}">{{ prop.status }}</span>
                <span class="prop-title">{{ prop.title }}</span>
            </summary>
            <div class="proposal-content">
                <p class="prop-desc">{{ prop.description }}</p>
                {% if prop.reason %}
                <p class="prop-reason"><strong>選定理由:</strong> {{ prop.reason }}</p>
                {% endif %}
                {% if prop.diff %}
                <div class="diff-container">
                    <div class="diff-header">
                        <span>生成コード差分 (Diff)</span>
                        <button class="full-code-btn" onclick="openFullCode('{{ prop.files_affected }}')">📄 全文を見る</button>
                    </div>
                    <div class="diff-block raw-diff" style="display:none;">{{ prop.diff }}</div>
                    <div class="diff-block formatted-diff"></div>
                </div>
                {% endif %}
                
                {% if prop.status == 'PENDING' %}
                <div class="proposal-actions" style="margin-top: 12px; display: flex; gap: 10px;">
                    <button class="action-btn apply-btn" onclick="applyProposal('{{ prop.id }}')">✅ 適用する (Apply)</button>
                    <button class="action-btn reject-btn" onclick="rejectProposal('{{ prop.id }}')">❌ 却下する (Reject)</button>
                </div>
                {% endif %}
            </div>
        </details>
        {% endfor %}
        <div id="prop-empty-msg" class="log-entry" style="display: none;"><span class="log-msg">このステータスの改修案はなかよ。</span></div>
    </div>
    
    <!-- 公開ログ (Voyage / Evolution) -->
    <div class="card">
        <h2>📖 公開ログ (Public Logs)</h2>
        <div id="public-logs-container">
            <div class="log-entry"><span class="log-msg">読み込み中ばい...</span></div>
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
    
    <!-- ファイル全文表示モーダル -->
    <div id="codeModal">
        <div class="modal-content">
            <div class="modal-header">
                <span class="modal-title" id="modalTitle">Loading...</span>
                <div class="modal-actions">
                    <button class="copy-btn" id="copyBtn" onclick="copyFullCode()">📋 コピー</button>
                    <button class="close-btn" onclick="closeModal()">閉じる</button>
                </div>
            </div>
            <div id="fullCodeView">コードを読み込み中...</div>
        </div>
    </div>
    
    <script>
        function filterProposals(status, btn) {
            document.querySelectorAll('.prop-tab-btn').forEach(b => b.classList.remove('active'));
            if(btn) btn.classList.add('active');
            
            let visibleCount = 0;
            document.querySelectorAll('.prop-item').forEach(e => {
                const propStatus = e.getAttribute('data-status');
                if (status === 'ALL' || propStatus === status) {
                    e.style.display = '';
                    visibleCount++;
                } else {
                    e.style.display = 'none';
                }
            });
            
            const emptyMsg = document.getElementById('prop-empty-msg');
            if(emptyMsg) {
                emptyMsg.style.display = visibleCount === 0 ? 'block' : 'none';
            }
        }

        // ページロード時に PENDING タブをデフォルトで適用
        document.addEventListener('DOMContentLoaded', () => {
            const pendingBtn = document.querySelector('.prop-tab-btn.active');
            filterProposals('PENDING', pendingBtn);
        });

        function filterLogs(level, btn) {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.log-entry').forEach(e => {
                e.style.display = (level === 'ALL' || e.dataset.level === level) ? '' : 'none';
            });
        }
        
        // 差分のリッチ表示（ハイライト処理）
        function parseDiffs() {
            document.querySelectorAll('.diff-container').forEach(container => {
                const rawDiff = container.querySelector('.raw-diff').textContent;
                const lines = rawDiff.split('\\n');
                let html = '';
                lines.forEach(line => {
                    const esc = line.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                    if (line.startsWith('+') && !line.startsWith('+++')) {
                        html += `<span class="diff-line add">${esc}</span>`;
                    } else if (line.startsWith('-') && !line.startsWith('---')) {
                        html += `<span class="diff-line del">${esc}</span>`;
                    } else if (line.startsWith('@@') || line.startsWith('---') || line.startsWith('+++')) {
                        html += `<span class="diff-line info">${esc}</span>`;
                    } else {
                        html += `<span class="diff-line">${esc}</span>`;
                    }
                });
                container.querySelector('.formatted-diff').innerHTML = html;
            });
        }
        
        // 全文表示モーダル
        function openFullCode(filename) {
            // カンマ区切りの場合は最初のファイルを開く
            const file = filename.split(',')[0].trim();
            if(!file) { alert("ファイル名が不明です。"); return; }
            
            document.getElementById('modalTitle').textContent = file;
            document.getElementById('fullCodeView').textContent = '読み込み中ばい...少し待ってね！🚢';
            document.getElementById('copyBtn').textContent = '📋 コピー';
            document.getElementById('codeModal').style.display = 'flex';
            
            fetch('/api/workspace-file?path=' + encodeURIComponent(file))
                .then(r => r.json())
                .then(data => {
                    if(data.error) {
                        document.getElementById('fullCodeView').textContent = 'エラー: ' + data.error;
                    } else {
                        document.getElementById('fullCodeView').textContent = data.content;
                    }
                })
                .catch(e => {
                    document.getElementById('fullCodeView').textContent = '通信エラーが発生したばい。';
                });
        }
        function closeModal() {
            document.getElementById('codeModal').style.display = 'none';
        }
        
        // 追加: 承認・却下のアクション処理
        function applyProposal(id) {
            if(!confirm("この改修案を本番環境（/src）に適用するばい！よかですか？")) return;
            fetch('/api/proposals/' + id + '/apply', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    alert(data.message || '適用処理を開始したばい！再起動まで少し待ってね。');
                    location.reload();
                })
                .catch(e => alert("エラー発生: " + e));
        }

        function rejectProposal(id) {
            if(!confirm("お蔵入り（却下）にするばい！本当に破棄してよか？")) return;
            fetch('/api/proposals/' + id + '/reject', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    alert(data.message || '却下処理が完了したばい！');
                    location.reload();
                })
                .catch(e => alert("エラー発生: " + e));
        }
        
        // 全文コピー
        function copyFullCode() {
            const code = document.getElementById('fullCodeView').textContent;
            navigator.clipboard.writeText(code).then(() => {
                const btn = document.getElementById('copyBtn');
                btn.textContent = '✅ コピー完了';
                setTimeout(() => { btn.textContent = '📋 コピー'; }, 2000);
            }).catch(err => {
                alert('コピーに失敗しましたばい: ' + err);
            });
        }
        
        // 公開ログの取得
        function fetchPublicLogs() {
            fetch('/api/public-logs')
                .then(r => r.json())
                .then(data => {
                    const container = document.getElementById('public-logs-container');
                    if (data.error) {
                        container.innerHTML = `<div class="log-entry"><span class="log-msg">${data.error}</span></div>`;
                        return;
                    }
                    if (data.logs.length === 0) {
                        container.innerHTML = '<div class="log-entry"><span class="log-msg">公開ログはまだなかよ。</span></div>';
                        return;
                    }
                    let html = '';
                    data.logs.forEach(log => {
                        html += `
                            <div class="public-log-item" onclick="openPublicLog('${log.category}', '${log.name}')">
                                <span class="log-cat">${log.category === 'voyage_log' ? '航海' : '進化'}</span>
                                <span class="log-name">${log.name}</span>
                                <span class="log-date">${log.mtime}</span>
                            </div>
                        `;
                    });
                    container.innerHTML = html;
                });
        }

        function openPublicLog(category, filename) {
            const path = category + '/' + filename;
            document.getElementById('modalTitle').textContent = filename;
            document.getElementById('fullCodeView').textContent = '読み込み中ばい...🚢';
            document.getElementById('codeModal').style.display = 'flex';
            
            fetch('/api/public-log-content?path=' + encodeURIComponent(path))
                .then(r => r.json())
                .then(data => {
                    if(data.error) {
                        document.getElementById('fullCodeView').textContent = 'エラー: ' + data.error;
                    } else {
                        document.getElementById('fullCodeView').textContent = data.content;
                    }
                });
        }

        // 初期化
        parseDiffs();
        fetchPublicLogs();
        setTimeout(() => { if(document.getElementById('codeModal').style.display === 'none') location.reload(); }, 30000);
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
        from shared.models import SystemState, SystemLog, AutoImprovementProposal
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
        
        proposals_raw = db.query(AutoImprovementProposal).order_by(AutoImprovementProposal.created_at.desc()).limit(10).all()
        proposals = []
        for p in proposals_raw:
            proposals.append({
                "id": p.id,
                "status": p.status,
                "title": p.title,
                "description": p.description,
                "reason": p.target_selection_reason,
                "diff": p.diff_content,
                "files_affected": p.files_affected or ""
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
        logs=logs,
        proposals=proposals
    )
    return HTMLResponse(content=rendered)

@app.get("/api/workspace-file")
async def get_workspace_file(path: str):
    """(Security Note: workspace のみ参照可能に制限する)"""
    import os
    base_dir = os.path.abspath("/app/workspace")
    target_path = os.path.abspath(os.path.join(base_dir, path))
    
    if not target_path.startswith(base_dir):
        return {"error": "不正なファイルパスへのアクセスばい！"}
    
    if not os.path.exists(target_path):
        return {"error": "まだファイルが作成されてないか、見つからんやったよ！"}
        
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()
            return {"content": content}
    except Exception as e:
        return {"error": f"ファイルの読み込みに失敗したばい：{str(e)}"}

INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "aynyan-secret-2828")

@app.post("/api/proposals/{proposal_id}/apply")
async def apply_proposal_api(proposal_id: str):
    """(Security Note: INTERNAL_TOKENを使ってdev-agentを叩く)"""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"http://dev-agent:8013/apply/{proposal_id}",
                headers={"X-Internal-Token": INTERNAL_TOKEN},
                timeout=10.0
            )
            if resp.status_code == 200:
                return {"status": "success", "message": f"{proposal_id} の適用を開始したばい！再起動ば待っとってね！"}
            else:
                return {"status": "error", "message": f"適用に失敗したかも... ステータスコード: {resp.status_code}"}
    except Exception as e:
        return {"status": "error", "message": f"通信エラーが発生したばい：{e}"}

@app.post("/api/proposals/{proposal_id}/reject")
async def reject_proposal_api(proposal_id: str):
    """(Security Note: DB(memory-service)を直接更新してREJECTにする)"""
    try:
        async with httpx.AsyncClient() as client:
            u_resp = await client.patch(f"http://memory-service:8003/proposals/{proposal_id}", json={"status": "REJECTED"})
            if u_resp.status_code == 200:
                return {"status": "success", "message": f"{proposal_id} の改修案を破棄したばい。"}
            return {"status": "error", "message": "破棄データの更新に失敗したばい...。"}
    except Exception as e:
        return {"status": "error", "message": f"通信エラーが発生したばい：{e}"}

from datetime import datetime

@app.get("/api/public-logs")
async def get_public_logs():
    """/mnt/hdd/logs/public 以下のファイルをリストアップする"""
    import os
    base_dir = "/mnt/hdd/logs/public"
    logs = []
    if not os.path.exists(base_dir):
        return {"logs": []}
    
    try:
        for cat in ["voyage_log", "evolution_log"]:
            cat_dir = os.path.join(base_dir, cat)
            if os.path.exists(cat_dir):
                files = os.listdir(cat_dir)
                for f in files:
                    if f.endswith(".md"):
                        fpath = os.path.join(cat_dir, f)
                        mtime = os.path.getmtime(fpath)
                        mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                        logs.append({
                            "category": cat,
                            "name": f,
                            "mtime": mtime_str,
                            "ts": mtime
                        })
        # 新しい順にソート
        logs.sort(key=lambda x: x["ts"], reverse=True)
        return {"logs": logs[:20]}
    except Exception as e:
        return {"error": str(e), "logs": []}

@app.get("/api/public-log-content")
async def get_public_log_content(path: str):
    """公開ログの内容を取得する"""
    import os
    base_dir = "/mnt/hdd/logs/public"
    target_path = os.path.abspath(os.path.join(base_dir, path))
    
    if not target_path.startswith(os.path.abspath(base_dir)):
        return {"error": "不正なファイルパスばい！"}
    
    if not os.path.exists(target_path):
        return {"error": "ファイルが見つからんやったよ！"}
        
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()
            return {"content": content}
    except Exception as e:
        return {"error": f"読み込み失敗：{str(e)}"}
