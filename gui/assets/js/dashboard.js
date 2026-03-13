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

function filterLogs(level, btn) {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.log-entry').forEach(e => {
        e.style.display = (level === 'ALL' || e.dataset.level === level) ? '' : 'none';
    });
}

function parseDiffs() {
    document.querySelectorAll('.diff-container').forEach(container => {
        const rawDiffEl = container.querySelector('.raw-diff');
        if (!rawDiffEl) return;
        const rawDiff = rawDiffEl.textContent;
        const lines = rawDiff.split('\n');
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

function openFullCode(filename) {
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

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    parseDiffs();
    fetchPublicLogs();
    
    // Auto-apply PENDING filter
    const pendingBtn = document.querySelector('.prop-tab-btn.active');
    if (pendingBtn) filterProposals('PENDING', pendingBtn);
    
    // Auto refresh
    setTimeout(() => { 
        if(document.getElementById('codeModal') && document.getElementById('codeModal').style.display === 'none') {
            location.reload(); 
        }
    }, 30000);
});
