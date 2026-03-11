import os
from datetime import datetime, timezone

def export_to_public_markdown(category: str, date_str: str, content: str, base_path: str = "/mnt/hdd/logs/public"):
    """
    指定されたカテゴリ（voyage_log, evolution_log等）と日付でMarkdownファイルを出力する。
    """
    try:
        # ディレクトリ作成
        target_dir = os.path.join(base_path, category)
        os.makedirs(target_dir, exist_ok=True)
        
        # ファイル名決定 (YYYY-MM-DD.md)
        filename = f"{date_str}.md"
        file_path = os.path.join(target_dir, filename)
        
        # 内容の書き込み
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        print(f"[PublicExporter] Exported {category} to {file_path}")
        return True
    except Exception as e:
        print(f"[PublicExporter] Failed to export: {e}")
        return False
