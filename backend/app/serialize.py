"""Shape database rows into API responses."""
from .models import LABELS, Claim, ClaimEvidence, Conflict, EvidenceUnit, Gap, Source


def label(level: int) -> str:
    return LABELS.get(level, "Team")


def source_out(s: Source) -> dict:
    return {
        "id": s.id, "kind": s.kind, "filename": s.filename, "uri": s.uri,
        "access_label": label(s.access_label), "status": s.status, "error": s.error,
        "unit_count": s.unit_count, "redactions": s.redactions, "coverage": s.coverage,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def evidence_out(u: EvidenceUnit, with_text: bool = True) -> dict:
    d = {
        "id": u.id, "code": u.code, "kind": u.kind, "source_id": u.source_id,
        "source": u.source.filename if u.source else None,
        "source_type": u.source.kind if u.source else None, "author": u.author,
        "date": u.occurred_at, "location": u.location, "access_label": label(u.access_label),
    }
    if with_text:
        d["text"] = u.text
    return d


def citation_out(c: ClaimEvidence, level: int) -> dict:
    ev = c.evidence
    visible = ev is not None and ev.access_label <= level
    return {
        "cited_code": c.cited_code, "quote": c.quote, "match": c.match, "match_score": c.match_score,
        "start": c.start, "end": c.end,
        "evidence": evidence_out(ev) if visible else None,
        "hidden": ev is not None and not visible,
    }


def claim_out(c: Claim, level: int, detail: bool = False) -> dict:
    d = {
        "id": c.id, "code": c.code, "type": c.type, "subject": c.subject, "statement": c.statement,
        "original_statement": c.original_statement, "status": c.status, "owner": c.owner,
        "owner_reassigned": c.owner_reassigned, "rationale": c.rationale, "confidence": c.confidence,
        "support": c.support, "support_reason": c.support_reason, "review_state": c.review_state,
        "reviewer_note": c.reviewer_note, "leaver_note": c.leaver_note,
        "access_label": label(c.access_label), "extractor": c.extractor,
        "gate1": "pass" if any(x.match == "exact" for x in c.citations) else "fail",
        "citation_count": len(c.citations),
    }
    d["citations"] = [citation_out(x, level) for x in c.citations] if detail else [
        {"cited_code": x.cited_code, "match": x.match, "source": x.evidence.source.filename
         if x.evidence is not None and x.evidence.access_label <= level else None}
        for x in c.citations
    ]
    return d


def gap_out(g: Gap) -> dict:
    return {"id": g.id, "kind": g.kind, "question": g.question, "status": g.status, "answer": g.answer,
            "claim_id": g.claim_id, "conflict_id": g.conflict_id, "source_id": g.source_id,
            "answer_evidence_id": g.answer_evidence_id, "access_label": label(g.access_label)}


def conflict_out(k: Conflict, side_a: list[dict], side_b: list[dict]) -> dict:
    return {"id": k.id, "kind": k.kind, "explanation": k.explanation, "status": k.status,
            "winner_claim_id": k.winner_claim_id, "resolution_note": k.resolution_note,
            "newer_side": k.newer_side, "access_label": label(k.access_label),
            "side_a": side_a, "side_b": side_b,
            "claim_a": side_a[0] if side_a else None, "claim_b": side_b[0] if side_b else None}
