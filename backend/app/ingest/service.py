"""Store parsed units as evidence: redact, hash, number (E-1, E-2 ...) and inherit the source's access label."""

import hashlib

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import EvidenceUnit, Source
from .guard import flags_for
from .parsers import ParsedSource
from .redact import redact


def _hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.lower().split()).encode()).hexdigest()


def next_seq(db: Session, project_id: str) -> int:
    current = db.query(func.max(EvidenceUnit.seq)).filter_by(project_id=project_id).scalar()
    return (current or 0) + 1


def store_units(db: Session, source: Source, parsed: ParsedSource) -> int:
    seq = next_seq(db, source.project_id)
    redactions = 0
    for unit in parsed.units:
        text, n = redact(unit.text)
        redactions += n
        db.add(
            EvidenceUnit(
                project_id=source.project_id,
                source_id=source.id,
                code=f"E-{seq}",
                seq=seq,
                kind=unit.kind,
                text=text,
                text_hash=_hash(text),
                author=unit.author or parsed.author,
                occurred_at=unit.occurred_at or parsed.occurred_at,
                location=unit.location,
                access_label=source.access_label,
                flags=flags_for(text),
            )
        )
        seq += 1
    source.unit_count = len(parsed.units)
    source.redactions = redactions
    source.coverage = {"units": len(parsed.units), "skipped": parsed.skipped[:50], "skipped_count": len(parsed.skipped)}
    flagged = sum(1 for u in parsed.units if flags_for(u.text))
    if flagged:
        source.coverage["flagged_instructions"] = flagged
    if parsed.unreadable or not parsed.units:
        source.status = "unreadable"
        source.error = "No readable text found." if not parsed.skipped else "; ".join(parsed.skipped[:3])
    else:
        source.status = "parsed"
        source.error = None
    return len(parsed.units)


def append_new_units(db: Session, source: Source, parsed: ParsedSource) -> int:
    """GitHub re-sync: store only items that are new or changed since the last sync (by text hash)."""
    have = {h for (h,) in db.query(EvidenceUnit.text_hash).filter_by(source_id=source.id)}
    seq = next_seq(db, source.project_id)
    added = 0
    for unit in parsed.units:
        text, n = redact(unit.text)
        h = _hash(text)
        if h in have:
            continue
        have.add(h)
        db.add(
            EvidenceUnit(
                project_id=source.project_id,
                source_id=source.id,
                code=f"E-{seq}",
                seq=seq,
                kind=unit.kind,
                text=text,
                text_hash=h,
                author=unit.author or parsed.author,
                occurred_at=unit.occurred_at or parsed.occurred_at,
                location=unit.location,
                access_label=source.access_label,
                flags=flags_for(text),
            )
        )
        source.redactions = (source.redactions or 0) + n
        seq += 1
        added += 1
    source.unit_count = (source.unit_count or 0) + added
    return added


def _scrub(value, unit_ids: set[str], codes: set[str]):
    """Remove every quoted piece of deleted evidence from stored JSON (handover snapshots, diffs, Ask answers).
    A handover line whose only evidence was deleted is removed entirely."""

    def gone(d: dict) -> bool:
        return d.get("evidence_id") in unit_ids or (("quote" in d or "text" in d) and d.get("code") in codes)

    if isinstance(value, list):
        out = []
        for v in value:
            if isinstance(v, dict):
                if gone(v):
                    continue
                ev = v.get("evidence")
                if isinstance(ev, list) and ev:
                    kept = _scrub(ev, unit_ids, codes)
                    if not kept:
                        continue
                    v = {**{k: _scrub(x, unit_ids, codes) for k, x in v.items()}, "evidence": kept}
                else:
                    v = _scrub(v, unit_ids, codes)
            elif isinstance(v, list):
                v = _scrub(v, unit_ids, codes)
            out.append(v)
        return out
    if isinstance(value, dict):
        return {k: _scrub(v, unit_ids, codes) for k, v in value.items()}
    return value


def delete_source_everywhere(db: Session, source: Source) -> dict:
    from ..models import APPROVED_STATES, Claim, ClaimEvidence, Conflict, Gap, HandoverVersion, Question
    from ..verify.service import refresh_confidence

    units = db.query(EvidenceUnit).filter_by(source_id=source.id).all()
    unit_ids, codes = {u.id for u in units}, {u.code for u in units}
    claims_removed = claims_rechecked = 0
    if unit_ids:
        cites = db.query(ClaimEvidence).filter(ClaimEvidence.evidence_id.in_(unit_ids)).all()
        touched = {c.claim_id for c in cites}
        for c in cites:
            db.delete(c)
        db.flush()
        for claim in db.query(Claim).filter(Claim.id.in_(touched)).all():
            db.refresh(claim)
            if not claim.citations and not claim.leaver_evidence_id:
                db.query(Gap).filter_by(claim_id=claim.id).delete()
                db.query(Conflict).filter((Conflict.claim_a_id == claim.id) | (Conflict.claim_b_id == claim.id)).delete(
                    synchronize_session=False
                )
                db.delete(claim)
                claims_removed += 1
            else:
                claim.support = None
                claim.support_reason = "A source this claim cited was deleted. Ask the AI again to re-check the remaining quotes."
                if claim.review_state in APPROVED_STATES:
                    from datetime import datetime, timezone

                    claim.changed_note = "A source this approved line relied on was deleted. Check it still holds."
                    claim.changed_at = datetime.now(timezone.utc)
                refresh_confidence(db, claim)
                claims_rechecked += 1
        for claim in db.query(Claim).filter_by(project_id=source.project_id).all():
            if claim.changed_evidence:
                claim.changed_evidence = _scrub(claim.changed_evidence, unit_ids, codes)
        for v in db.query(HandoverVersion).filter_by(project_id=source.project_id).all():
            v.snapshot = _scrub(v.snapshot, unit_ids, codes)
            v.diff = _scrub(v.diff, unit_ids, codes) if v.diff else v.diff
        for q in db.query(Question).filter_by(project_id=source.project_id).all():
            if q.citations:
                q.citations = _scrub(q.citations, unit_ids, codes)
        db.query(EvidenceUnit).filter_by(source_id=source.id).delete(synchronize_session=False)
    db.query(Gap).filter_by(project_id=source.project_id, source_id=source.id).delete(synchronize_session=False)
    db.delete(source)
    db.flush()
    return {"evidence_removed": len(unit_ids), "claims_removed": claims_removed, "claims_to_recheck": claims_rechecked}
