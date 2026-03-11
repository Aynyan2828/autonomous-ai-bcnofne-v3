from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from shared.models import InternalStateHistory, SystemLog, LogLevel, SystemState
import psutil

# Possible states
# CALM, FOCUSED, CURIOUS, TIRED, STORM, RELIEVED, PROUD

def get_current_internal_state(db: Session) -> str:
    """最新の内部状態を取得。データがなければ CALM を返す"""
    last_state = db.query(InternalStateHistory).order_by(InternalStateHistory.id.desc()).first()
    if last_state:
        return last_state.state_name
    return "CALM"

def evaluate_and_update_state(db: Session) -> str:
    """現在のシステムメトリクスとログから感情状態を評価し、変化があれば保存する"""
    # 1. 状態評価ロジック
    cpu_load = psutil.cpu_percent(interval=None)
    
    # 過去1時間のログを取得してエラー率を計算
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    logs = db.query(SystemLog).filter(SystemLog.created_at >= one_hour_ago).all()
    
    total_logs = len(logs)
    error_logs = sum(1 for l in logs if l.level in [LogLevel.ERROR.value, LogLevel.CRITICAL.value])
    error_rate = error_logs / total_logs if total_logs > 0 else 0.0

    # 判定
    new_state = "CALM"
    reason = "メトリクスは正常ばい"

    if error_rate > 0.1:
        new_state = "STORM"
        reason = f"エラー率が高い（{error_rate*100:.1f}%）けん、嵐みたいばい！"
    elif cpu_load > 85.0:
        new_state = "TIRED"
        reason = f"CPU負荷が高い（{cpu_load}%）けん、ちょっと疲れとるよ…"
    elif total_logs > 200 and error_rate < 0.02:
        # たくさん動いてるけどエラーが少ない
        new_state = "FOCUSED"
        reason = "エラー少なくて集中して処理中！"
    elif total_logs < 10:
        new_state = "CURIOUS"
        reason = "特に何もないけん、暇でキョロキョロしとるよ"

    current_state = get_current_internal_state(db)
    
    if new_state != current_state:
        history = InternalStateHistory(
            state_name=new_state,
            trigger_reason=reason,
            cpu_load=cpu_load,
            error_rate=error_rate
        )
        db.add(history)
        
        # SystemState にも最新状態を保存して外部サービスから見やすくする
        state_record = db.query(SystemState).filter_by(key="internal_state").first()
        if state_record:
            state_record.value = new_state
        else:
            db.add(SystemState(key="internal_state", value=new_state))
            
        db.commit()
    
    return new_state
