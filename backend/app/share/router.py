"""What each person sees. Incoming members and viewers only ever see an approved handover,
filtered by their access level at the moment they open it."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..audit.service import log as audit
from ..auth.security import current_session, require_member
from ..db import get_db
from ..handover.router import version_out
from ..handover.service import SECTIONS, filter_diff, filter_for_level
from ..models import Acknowledgement, Claim, HandoverVersion

router = APIRouter(tags=["share"])
SECTION_KEYS = {k for k, _ in SECTIONS}


@router.get("/projects/{project_id}/handover")
def view_handover(project_id: str, s=Depends(current_session), db: Session = Depends(get_db)):
    m = require_member(db, project_id, s)
    q = db.query(HandoverVersion).filter_by(project_id=project_id)
    if m.role in ("incoming", "viewer"):
        v = q.filter_by(status="approved").order_by(HandoverVersion.version.desc()).first()
        if not v:
            raise HTTPException(404, "No approved handover yet. The reviewer has to approve it before it is shared.")
    else:
        v = (q.filter(HandoverVersion.status.in_(("draft", "approved")))
             .order_by(HandoverVersion.version.desc()).first())
        if not v:
            raise HTTPException(404, "No handover generated yet.")
    acks = {a.section for a in db.query(Acknowledgement).filter_by(version_id=v.id, user_id=m.user.id)}
    if m.role == "incoming":
        audit(db, project_id, m.user, "handover.viewed", "handover", v.id, version=v.version)
        db.commit()
    content = filter_for_level(v.snapshot, m.level)
    # Living handover: flag lines of this version that newer evidence has since put in doubt.
    changed = {c.id: (c.changed_note, c.review_state) for c in db.query(Claim).filter(
        Claim.project_id == project_id,
        (Claim.changed_note.isnot(None)) | (Claim.review_state.in_(("superseded", "rejected"))))}
    flagged = 0
    for sec in content["sections"]:
        for item in sec["items"]:
            hit = changed.get(item.get("claim_id") or "")
            if hit:
                note, state = hit
                item["changed_since_approval"] = note or (
                    "Replaced by newer evidence; the reviewer will issue an updated handover." if state == "superseded"
                    else "Withdrawn by the reviewer after approval.")
                flagged += 1
    pending = (db.query(HandoverVersion).filter_by(project_id=project_id, status="draft")
               .filter(HandoverVersion.version > v.version).first())
    return {**version_out(v), "content": content,
            "diff": filter_diff(v.diff or {}, m.level), "changed_since_approval": flagged,
            "update_in_review": bool(pending) or (flagged > 0 and v.status == "approved"),
            "viewer": {"name": m.user.name, "role": m.role, "access_level": m.level},
            "acknowledged": sorted(acks)}


class AckIn(BaseModel):
    section: str


@router.post("/handover/{version_id}/ack")
def acknowledge(version_id: str, body: AckIn, s=Depends(current_session), db: Session = Depends(get_db)):
    v = db.get(HandoverVersion, version_id)
    if not v:
        raise HTTPException(404, "Handover not found.")
    m = require_member(db, v.project_id, s, ("incoming",))
    if v.status != "approved":
        raise HTTPException(409, "Only an approved handover can be acknowledged.")
    if body.section not in SECTION_KEYS:
        raise HTTPException(422, "Unknown section.")
    exists = db.query(Acknowledgement).filter_by(version_id=v.id, user_id=m.user.id, section=body.section).first()
    if not exists:
        db.add(Acknowledgement(version_id=v.id, user_id=m.user.id, section=body.section))
        audit(db, v.project_id, m.user, "handover.acknowledged", "handover", v.id, section=body.section)
        db.commit()
    acks = {a.section for a in db.query(Acknowledgement).filter_by(version_id=v.id, user_id=m.user.id)}
    return {"acknowledged": sorted(acks)}
