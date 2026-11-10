"""Gaps, conflicts and the departure interview."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..audit.service import log as audit
from ..auth.security import CAN_REVIEW, CAN_SEE_WORKING, current_session, require_member
from ..db import get_db
from ..ingest.service import next_seq, _hash
from ..ingest.redact import redact
from ..models import Claim, Conflict, EvidenceUnit, Gap, Source
from ..serialize import claim_out, conflict_out, gap_out
from ..verify.service import refresh_confidence

router = APIRouter(tags=["gaps & conflicts"])


@router.get("/projects/{project_id}/gaps")
def list_gaps(project_id: str, s=Depends(current_session), db: Session = Depends(get_db)):
    m = require_member(db, project_id, s, CAN_SEE_WORKING)
    rows = db.query(Gap).filter(Gap.project_id == project_id, Gap.access_label <= m.level).all()
    order = {"open": 0, "answered": 1, "dismissed": 2}
    rows.sort(key=lambda g: order.get(g.status, 3))
    return {"gaps": [gap_out(g) for g in rows],
            "hidden_count": db.query(Gap).filter(Gap.project_id == project_id, Gap.access_label > m.level).count()}


class AnswerIn(BaseModel):
    answer: str = Field(min_length=2, max_length=2000)


def _attestation_source(db: Session, project_id: str, level: int, name: str) -> Source:
    src = db.query(Source).filter_by(project_id=project_id, kind="attestation", access_label=level).first()
    if not src:
        src = Source(project_id=project_id, kind="attestation", filename=f"Departure interview — {name}",
                     access_label=level, status="parsed")
        db.add(src)
        db.flush()
    return src


@router.post("/gaps/{gap_id}/answer")
def answer_gap(gap_id: str, body: AnswerIn, s=Depends(current_session), db: Session = Depends(get_db)):
    g = db.get(Gap, gap_id)
    if not g:
        raise HTTPException(404, "Question not found.")
    m = require_member(db, g.project_id, s, ("departing",))
    if g.access_label > m.level:
        raise HTTPException(404, "Question not found.")
    if g.status != "open":
        raise HTTPException(409, "This question was already handled.")
    text, _ = redact(body.answer.strip())
    src = _attestation_source(db, g.project_id, g.access_label, m.user.name)
    seq = next_seq(db, g.project_id)
    unit = EvidenceUnit(project_id=g.project_id, source_id=src.id, code=f"E-{seq}", seq=seq, kind="attestation",
                        text=text, text_hash=_hash(text), author=m.user.name, access_label=g.access_label,
                        location={"gap_id": g.id, "question": g.question})
    db.add(unit)
    db.flush()
    src.unit_count += 1
    g.status, g.answer, g.answer_evidence_id = "answered", text, unit.id
    if g.claim_id:
        c = db.get(Claim, g.claim_id)
        if c:
            c.leaver_note = text
            c.leaver_evidence_id = unit.id
            if g.kind == "missing_reason" and not c.rationale:
                c.rationale = text
            refresh_confidence(db, c)
    if g.conflict_id:
        k = db.get(Conflict, g.conflict_id)
        if k:
            k.resolution_note = f"Leaver says: {text}"
    audit(db, g.project_id, m.user, "gap.answered", "gap", g.id, evidence=unit.code)
    db.commit()
    return gap_out(g)


class DismissIn(BaseModel):
    reason: str = Field(min_length=2, max_length=500)


@router.post("/gaps/{gap_id}/dismiss")
def dismiss_gap(gap_id: str, body: DismissIn, s=Depends(current_session), db: Session = Depends(get_db)):
    g = db.get(Gap, gap_id)
    if not g:
        raise HTTPException(404, "Question not found.")
    m = require_member(db, g.project_id, s, CAN_REVIEW)
    g.status = "dismissed"
    g.answer = f"Dismissed by reviewer: {body.reason.strip()}"
    audit(db, g.project_id, m.user, "gap.dismissed", "gap", g.id, reason=body.reason)
    db.commit()
    return gap_out(g)


def _sides(db: Session, k: Conflict, level: int) -> tuple[list[dict], list[dict]]:
    def load(ids):
        out = []
        for cid in ids or []:
            c = db.get(Claim, cid)
            if c and c.access_label <= level:
                out.append(claim_out(c, level, detail=True))
        return out
    return load(k.side_a or [k.claim_a_id]), load(k.side_b or [k.claim_b_id])


@router.get("/projects/{project_id}/conflicts")
def list_conflicts(project_id: str, s=Depends(current_session), db: Session = Depends(get_db)):
    m = require_member(db, project_id, s, CAN_SEE_WORKING)
    rows = db.query(Conflict).filter(Conflict.project_id == project_id, Conflict.access_label <= m.level).all()
    order = {"open": 0, "kept": 1, "resolved": 2}
    rows.sort(key=lambda k: order.get(k.status, 3))
    return {"conflicts": [conflict_out(k, *_sides(db, k, m.level)) for k in rows]}


class ResolveIn(BaseModel):
    winner_claim_id: str | None = None
    keep_both: bool = False
    note: str = Field(default="", max_length=1000)


@router.post("/conflicts/{conflict_id}/resolve")
def resolve_conflict(conflict_id: str, body: ResolveIn, s=Depends(current_session), db: Session = Depends(get_db)):
    k = db.get(Conflict, conflict_id)
    if not k:
        raise HTTPException(404, "Conflict not found.")
    m = require_member(db, k.project_id, s, CAN_REVIEW)
    if k.access_label > m.level:
        raise HTTPException(404, "Conflict not found.")
    side_a, side_b = list(k.side_a or [k.claim_a_id]), list(k.side_b or [k.claim_b_id])
    note = body.note.strip()
    if body.keep_both:
        k.status = "kept"
    else:
        if body.winner_claim_id in side_a:
            losers = side_b
        elif body.winner_claim_id in side_b:
            losers = side_a
        else:
            raise HTTPException(422, "Pick which side is current, or choose to keep both visible.")
        for cid in losers:
            c = db.get(Claim, cid)
            if c:
                c.review_state = "superseded"
                c.reviewer_note = f"Superseded when resolving a conflict. {note}".strip()
        k.status, k.winner_claim_id = "resolved", body.winner_claim_id
    if note:
        k.resolution_note = ((k.resolution_note + " | ") if k.resolution_note else "") + f"Reviewer: {note}"
    db.flush()
    for cid in side_a + side_b:
        c = db.get(Claim, cid)
        if c:
            refresh_confidence(db, c)
    for g in db.query(Gap).filter_by(conflict_id=k.id, status="open"):
        g.status, g.answer = "dismissed", "Resolved by reviewer."
    audit(db, k.project_id, m.user, "conflict.resolved", "conflict", k.id, keep_both=body.keep_both,
          winner=body.winner_claim_id, note=note, kind=k.kind)
    db.commit()
    return conflict_out(k, *_sides(db, k, m.level))
