from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..auth.security import CAN_SEE_WORKING, current_session, require_member
from ..db import get_db
from ..models import EvidenceUnit
from ..serialize import evidence_out

router = APIRouter(tags=["evidence"])


@router.get("/projects/{project_id}/evidence")
def list_evidence(project_id: str, source_id: str | None = None, q: str | None = None, limit: int = 300,
                  s=Depends(current_session), db: Session = Depends(get_db)):
    m = require_member(db, project_id, s, CAN_SEE_WORKING)
    query = db.query(EvidenceUnit).filter(EvidenceUnit.project_id == project_id,
                                          EvidenceUnit.access_label <= m.level)  # permission filter in SQL
    if source_id:
        query = query.filter(EvidenceUnit.source_id == source_id)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(EvidenceUnit.text.ilike(like), EvidenceUnit.code.ilike(like)))
    rows = query.order_by(EvidenceUnit.seq).limit(min(limit, 1000)).all()
    hidden = db.query(EvidenceUnit).filter(EvidenceUnit.project_id == project_id,
                                           EvidenceUnit.access_label > m.level).count()
    return {"evidence": [evidence_out(u) for u in rows], "hidden_count": hidden}


@router.get("/evidence/{evidence_id}")
def get_evidence(evidence_id: str, s=Depends(current_session), db: Session = Depends(get_db)):
    u = db.get(EvidenceUnit, evidence_id)
    if not u:
        raise HTTPException(404, "Evidence not found.")
    m = require_member(db, u.project_id, s)
    if u.access_label > m.level:
        raise HTTPException(403, "This evidence comes from a source above your access level.")
    return evidence_out(u)
