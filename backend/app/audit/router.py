from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth.security import CAN_REVIEW, current_session, require_member
from ..db import get_db
from ..models import AuditEvent

router = APIRouter(tags=["audit"])


@router.get("/projects/{project_id}/audit")
def list_audit(project_id: str, limit: int = 200, s=Depends(current_session), db: Session = Depends(get_db)):
    require_member(db, project_id, s, CAN_REVIEW)
    rows = (db.query(AuditEvent).filter_by(project_id=project_id)
            .order_by(AuditEvent.id.desc()).limit(min(limit, 500)).all())
    return [
        {"id": r.id, "at": r.at.isoformat(), "actor": r.actor_name, "action": r.action,
         "target_type": r.target_type, "target_id": r.target_id, "detail": r.detail}
        for r in rows
    ]
