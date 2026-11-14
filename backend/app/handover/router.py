from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..audit.service import log as audit
from ..auth.security import CAN_REVIEW, current_session, require_member
from ..db import get_db
from ..models import APPROVED_STATES, Acknowledgement, Claim, Conflict, HandoverVersion
from .service import build_snapshot, diff_snapshots

router = APIRouter(tags=["handover"])


def version_out(v: HandoverVersion) -> dict:
    return {"id": v.id, "version": v.version, "status": v.status,
            "created_at": v.created_at.isoformat(),
            "approved_at": v.approved_at.isoformat() if v.approved_at else None,
            "approved_by": v.approved_by, "changes": (v.diff or {}).get("total"),
            "base_version": (v.diff or {}).get("base_version")}


@router.post("/projects/{project_id}/handover/generate")
def generate(project_id: str, s=Depends(current_session), db: Session = Depends(get_db)):
    m = require_member(db, project_id, s, CAN_REVIEW)
    approved = db.query(Claim).filter(Claim.project_id == project_id,
                                      Claim.review_state.in_(APPROVED_STATES)).count()
    if not approved:
        raise HTTPException(409, "Approve at least one claim before generating the handover.")
    if db.query(Conflict).filter_by(project_id=project_id, status="open").count():
        raise HTTPException(409, "Resolve open conflicts first (or choose to keep both sides visible).")
    db.query(HandoverVersion).filter_by(project_id=project_id, status="draft").update({"status": "superseded"})
    n = (db.query(func.max(HandoverVersion.version)).filter_by(project_id=project_id).scalar() or 0) + 1
    snapshot = build_snapshot(db, m.project)
    base = (db.query(HandoverVersion).filter_by(project_id=project_id, status="approved")
            .order_by(HandoverVersion.version.desc()).first())
    diff = diff_snapshots(base.snapshot if base else None, snapshot)
    if base:
        diff["base_version"] = base.version
    v = HandoverVersion(project_id=project_id, version=n, status="draft", snapshot=snapshot, diff=diff,
                        created_by=m.user.id)
    db.add(v)
    db.flush()
    audit(db, project_id, m.user, "handover.generated", "handover", v.id, version=n, approved_claims=approved)
    db.commit()
    return version_out(v)


@router.post("/handover/{version_id}/approve")
def approve(version_id: str, s=Depends(current_session), db: Session = Depends(get_db)):
    v = db.get(HandoverVersion, version_id)
    if not v:
        raise HTTPException(404, "Handover not found.")
    m = require_member(db, v.project_id, s, CAN_REVIEW)
    if v.status != "draft":
        raise HTTPException(409, f"Only a draft can be approved (this one is {v.status}).")
    previous = (db.query(HandoverVersion).filter_by(project_id=v.project_id, status="approved")
                .order_by(HandoverVersion.version.desc()).first())
    db.query(HandoverVersion).filter_by(project_id=v.project_id, status="approved").update({"status": "superseded"})
    v.status, v.approved_by, v.approved_at = "approved", s.real_user.name, datetime.now(timezone.utc)
    carried = 0
    if previous:
        # Sections that didn't change keep their acknowledgements; changed ones must be read again.
        changed = set((v.diff or {}).get("sections", {}).keys())
        for a in db.query(Acknowledgement).filter_by(version_id=previous.id).all():
            if a.section not in changed:
                db.add(Acknowledgement(version_id=v.id, user_id=a.user_id, section=a.section))
                carried += 1
    audit(db, v.project_id, m.user, "handover.approved", "handover", v.id, version=v.version,
          changes=(v.diff or {}).get("total", 0), acknowledgements_carried_over=carried)
    db.commit()
    return version_out(v)


@router.get("/projects/{project_id}/handover/versions")
def versions(project_id: str, s=Depends(current_session), db: Session = Depends(get_db)):
    require_member(db, project_id, s, CAN_REVIEW)
    rows = db.query(HandoverVersion).filter_by(project_id=project_id).order_by(HandoverVersion.version.desc()).all()
    return [version_out(v) for v in rows]
