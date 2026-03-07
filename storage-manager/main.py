import os
import sys
import shutil
import time
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from typing import List

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = FastAPI(title="shipOS Storage Manager")

SSD_MOUNT = os.getenv("SSD_MOUNT_PATH", "/mnt/ssd/share")
HDD_MOUNT = os.getenv("HDD_MOUNT_PATH", "/mnt/hdd/share")

EXCLUDE_DIRS = [".git", "docker_volumes", "system_config"]
EXCLUDE_EXTS = [".db", ".env"]

class TieringResult(BaseModel):
    dry_run: bool
    candidates: List[str]
    total_size_mb: float

def is_excluded(filepath: str) -> bool:
    name = os.path.basename(filepath)
    if any(name.startswith(ex) for ex in EXCLUDE_DIRS):
        return True
    if any(filepath.endswith(ext) for ext in EXCLUDE_EXTS):
        return True
    # shipos.db などの必須ファイル除外
    if name == "shipos.db":
        return True
    return False

def find_old_files(directory: str, days_old: int = 30) -> List[str]:
    candidates = []
    if not os.path.exists(directory):
        return candidates

    current_time = time.time()
    for root, dirs, files in os.walk(directory):
        # Exclude directories in-place
        dirs[:] = [d for d in dirs if not is_excluded(os.path.join(root, d))]
        
        for file in files:
            filepath = os.path.join(root, file)
            if is_excluded(filepath):
                continue
            
            try:
                stat = os.stat(filepath)
                # 最終アクセス時刻と更新時刻のどちらか新しい方を見る場合もあるが、要件に合わせて更新時刻を使用
                mtime = stat.st_mtime
                age_days = (current_time - mtime) / (24 * 3600)
                if age_days >= days_old:
                    candidates.append(filepath)
            except Exception as e:
                print(f"Error reading file {filepath}: {e}")
                
    return candidates

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "storage-manager"}

@app.get("/tiering/dry-run", response_model=TieringResult)
def dry_run_tiering(days: int = 30):
    """HDDへ移動すべきSSD上の候補ファイル一覧を返す"""
    candidates = find_old_files(SSD_MOUNT, days_old=days)
    
    total_bytes = 0
    for c in candidates:
        try:
            total_bytes += os.path.getsize(c)
        except:
            pass
            
    return {"dry_run": True, "candidates": candidates, "total_size_mb": total_bytes / (1024 * 1024)}

@app.post("/tiering/execute")
def execute_tiering(days: int = 30):
    """実際のSSD->HDDの移動を実行する。Coreからの許可が必要なLevel 3アクション想定。"""
    candidates = find_old_files(SSD_MOUNT, days_old=days)
    
    if not os.path.exists(HDD_MOUNT):
        raise HTTPException(status_code=500, detail="HDD mount path not found.")
        
    moved_count = 0
    for filepath in candidates:
        try:
            # 宛先のディレクトリ構造を維持しつつ移動
            rel_path = os.path.relpath(filepath, SSD_MOUNT)
            dest_path = os.path.join(HDD_MOUNT, rel_path)
            dest_dir = os.path.dirname(dest_path)
            
            os.makedirs(dest_dir, exist_ok=True)
            shutil.move(filepath, dest_path)
            moved_count += 1
        except Exception as e:
            print(f"Failed to move {filepath}: {e}")
            
    return {"status": "success", "moved_files_count": moved_count}
