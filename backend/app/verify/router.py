"""Claims: list, inspect verification, and the reviewer's decisions."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..audit.service import log as audit
from ..auth.security import CAN_REVIEW, CAN_SEE_WORKING, current_session, require_member
from ..db import get_db
from ..models import Claim, Conflict, Review
from ..serialize import claim_out
from .service import conflict_members, open_conflicts_for, refresh_confidence, valid_citations

router = APIRouter(tags=["claims"])


@router.get("/projects/{project_id}/claims")
def list_claims(project_id: str, type: str | None = None, confidence: str | None = None,
                review_state: str | None = None, q: str | None = None,
                s=Depends(current_session), db: Session = Depends(get_db)):
    m = require_member(db, project_id, s, CAN_SEE_WORKING)
    query = db.query(Claim).filter(Claim.project_id == project_id, Claim.access_label <= m.level)
    if type:
        query = query.filter(Claim.type == type)
    if confidence:
        query = query.filter(Claim.confidence == confidence)
    if review_state:
        query = query.filter(Claim.review_state == review_state)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(Claim.statement.ilike(like), Claim.subject.ilike(like), Claim.code.ilike(like)))
    rows = query.order_by(Claim.created_at, Claim.code).all()
    rows.sort(key=lambda c: int(c.code.split("-")[1]) if c.code.split("-")[-1].isdigit() else 0)
    hidden = db.query(Claim).filter(Claim.project_id == project_id, Claim.access_label > m.level).count()
    return {"claims": [claim_out(c, m.level) for c in rows], "hidden_count": hidden}


@router.get("/claims/{claim_id}")
def get_claim(claim_id: str, s=Depends(current_session), db: Session = Depends(get_db)):
    c = db.get(Claim, claim_id)
    if not c:
        raise HTTPException(404, "Claim not found.")
    m = require_member(db, c.project_id, s, CAN_SEE_WORKING)
    if c.access_label > m.level:
        raise HTTPException(404, "Claim not found.")
    out = claim_out(c, m.level, detail=True)
    out["reviews"] = [{"action": r.action, "reason": r.reason, "at": r.at.isoformat(), "before": r.before,
                       "after": r.after} for r in db.query(Review).filter_by(claim_id=c.id).order_by(Review.id)]
    conflicts = [k for k in db.query(Conflict).filter(Conflict.project_id == c.project_id) if c.id in conflict_members(k)]
    out["conflicts"] = [{"id": k.id, "status": k.status, "explanation": k.explanation} for k in conflicts]
    return out


class ReviewIn(BaseModel):
    action: Literal["approve", "reject", "edit", "reassign", "reset"]
    statement: str | None = Field(default=None, max_length=1000)
    owner: str | None = Field(default=None, max_length=160)
    reason: str | None = Field(default=None, max_length=1000)


def _snap(c: Claim) -> dict:
    return {"statement": c.statement, "owner": c.owner, "review_state": c.review_state, "confidence": c.confidence}


@router.post("/claims/{claim_id}/review")
def review_claim(claim_id: str, body: ReviewIn, s=Depends(current_session), db: Session = Depends(get_db)):
    c = db.get(Claim, claim_id)
    if not c:
        raise HTTPException(404, "Claim not found.")
    m = require_member(db, c.project_id, s, CAN_REVIEW)
    if c.access_label > m.level:
        raise HTTPException(404, "Claim not found.")
    before = _snap(c)

    if body.action == "approve":
        if open_conflicts_for(db, c, ("open",)):
            raise HTTPException(409, "This claim is part of an unresolved conflict. Resolve the conflict first.")
        if c.review_state == "superseded":
            raise HTTPException(409, "This claim lost a conflict resolution and can't be approved.")
        if c.confidence == "unverified":
            # Unverified claims never enter the handover as verified facts.
            if not (body.reason and body.reason.strip()):
                raise HTTPException(422, "This claim failed verification. Add a reason to approve it as "
                                         "reviewer-asserted, or reject it.")
            c.confidence = "reviewer_asserted"
            c.reviewer_note = body.reason.strip()
        c.review_state = "approved"
    elif body.action == "reject":
        c.review_state = "rejected"
        c.reviewer_note = (body.reason or "").strip() or c.reviewer_note
    elif body.action == "edit":
        text = (body.statement or "").strip()
        if not text:
            raise HTTPException(422, "Write the corrected statement.")
        if text != c.statement:
            if open_conflicts_for(db, c, ("open",)):
                raise HTTPException(409, "This claim is part of an unresolved conflict. Resolve the conflict first.")
            c.statement = text
            c.confidence = "reviewer_asserted"
            c.reviewer_note = (body.reason or "Corrected by reviewer").strip()
            # A corrected claim is the reviewer's own statement; it may enter the handover, clearly labelled.
            c.review_state = "corrected"
    elif body.action == "reassign":
        owner = (body.owner or "").strip()
        if not owner:
            raise HTTPException(422, "Name the new owner.")
        c.owner = owner
        c.owner_reassigned = True
    elif body.action == "reset":
        c.review_state = "pending"
        if c.confidence == "reviewer_asserted" and c.statement == c.original_statement:
            c.reviewer_note = None
            c.confidence = "unverified"
            refresh_confidence(db, c)

    db.add(Review(claim_id=c.id, reviewer_id=m.user.id, action=body.action, before=before, after=_snap(c),
                  reason=body.reason))
    audit(db, c.project_id, m.user, f"claim.{body.action}", "claim", c.id, code=c.code,
          valid_citations=len(valid_citations(c)), reason=body.reason)
    db.commit()
    return claim_out(c, m.level, detail=True)
