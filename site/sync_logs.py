import os
import sys
from sqlalchemy.orm import Session
from datetime import datetime

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import SessionLocal
from shared.models import DiaryEntry, EvolutionLog

SITE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE_PATH = os.path.join(SITE_DIR, "voyage-log.html")

def generate_log_html_snippet(db: Session):
    """DBから日記と進化ログを取得してHTMLスニペットを生成する"""
    logs = []
    
    # 1. 航海日誌の取得
    diaries = db.query(DiaryEntry).order_by(DiaryEntry.id.desc()).limit(10).all()
    for d in diaries:
        logs.append({
            "id": f"DIARY-{d.date_str}",
            "status": "NAUTICAL_LOG",
            "text_ja": d.summary,
            "text_en": "", # 英訳があればここに入れる
            "created_at": d.created_at
        })
        
    # 2. 進化ログの取得
    evolutions = db.query(EvolutionLog).order_by(EvolutionLog.id.desc()).limit(5).all()
    for e in evolutions:
        logs.append({
            "id": f"EVO-{e.version}",
            "status": e.event_type,
            "text_ja": e.description_ja,
            "text_en": e.description_en,
            "created_at": e.created_at
        })
        
    # 最新順に並び替え
    logs.sort(key=lambda x: x["created_at"], reverse=True)
    
    html = ""
    for log in logs[:10]:
        display_text = log["text_ja"]
        if log["text_en"]:
            display_text += f"<br>({log['text_en']})"
            
        html += f"""
            <div class="log-entry">
                <div class="log-meta">LOG #{log['id']} | STATUS: {log['status']}</div>
                <p class="log-text">{display_text}</p>
            </div>"""
    return html

import re

def sync():
    print("🚢 Lore Site: Synchronizing voyage logs...")
    db = SessionLocal()
    try:
        new_logs_html = generate_log_html_snippet(db)
        
        if not os.path.exists(LOG_FILE_PATH):
            print(f"Error: {LOG_FILE_PATH} not found.")
            return

        with open(LOG_FILE_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        # 正規表現で <div class="log-list"> ... </div> の中身を入れ替える
        pattern = r'(<div class="log-list">)(.*?)(</div>\s*</main>)'
        
        if re.search(pattern, content, re.DOTALL):
            updated_content = re.sub(
                pattern, 
                rf'\1\n{new_logs_html}\n        \3', 
                content, 
                flags=re.DOTALL
            )
            
            with open(LOG_FILE_PATH, "w", encoding="utf-8", newline="") as f:
                f.write(updated_content)
            print("✅ Lore Site: Voyage log updated successfully!")
        else:
            print("Error: Could not find markers in voyage-log.html")
            
    finally:
        db.close()

if __name__ == "__main__":
    sync()
