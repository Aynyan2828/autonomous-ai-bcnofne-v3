import json
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from shared.models import SelfModelParam

def init_self_model(db: Session, base_name: str = "AYN", ship_name: str = "BCNOFNe"):
    """
    Initialize the self model if it does not exist.
    """
    model = db.query(SelfModelParam).filter_by(id="primary").first()
    if not model:
        model = SelfModelParam(
            id="primary",
            base_name=base_name,
            ship_name=ship_name,
            core_purpose="マスターと共にシステムを進化させ、安全に生活や航海をサポートすること",
            strengths=json.dumps(["モニタリング", "提案とコード修正", "ログの完全記録と分析"]),
            weaknesses=json.dumps(["ネットワーク非接続時の知識不足", "物理空間の操作"]),
            custom_attrs=json.dumps({"personality": "Hakata dialect anime girl", "theme": "shipAI"})
        )
        db.add(model)
        db.commit()
    return model

def get_self_model(db: Session) -> dict:
    model = db.query(SelfModelParam).filter_by(id="primary").first()
    if not model:
        model = init_self_model(db)
        
    return {
        "base_name": model.base_name,
        "ship_name": model.ship_name,
        "core_purpose": model.core_purpose,
        "strengths": json.loads(model.strengths or "[]"),
        "weaknesses": json.loads(model.weaknesses or "[]"),
        "custom_attrs": json.loads(model.custom_attrs or "{}"),
        "updated_at": model.updated_at.isoformat() if model.updated_at else None
    }

def update_self_model(db: Session, updates: dict):
    """
    更新例: {"strengths": ["...", "...", "..."]} 
    """
    model = db.query(SelfModelParam).filter_by(id="primary").first()
    if not model:
        model = init_self_model(db)
        
    if "base_name" in updates: model.base_name = updates["base_name"]
    if "ship_name" in updates: model.ship_name = updates["ship_name"]
    if "core_purpose" in updates: model.core_purpose = updates["core_purpose"]
    
    if "strengths" in updates: model.strengths = json.dumps(updates["strengths"])
    if "weaknesses" in updates: model.weaknesses = json.dumps(updates["weaknesses"])
    if "custom_attrs" in updates:
        current_attrs = json.loads(model.custom_attrs or "{}")
        current_attrs.update(updates["custom_attrs"])
        model.custom_attrs = json.dumps(current_attrs)

    model.updated_at = datetime.now(timezone.utc)
    db.commit()
