"""Evidence verification — Baton's core differentiator.

Gate 1 (quote existence) is plain code: the cited evidence must exist in this project and contain the
quote word for word (after normalising only spaces, letter case and curly quotes/dashes). A quote with
changed words or punctuation is NOT accepted; RapidFuzz is used only to show how close it came and
where, so the reviewer can see what the AI altered.
Gate 2 (claim support) is a separate AI call that sees only the claim and its quotes.
Confidence labels come from both gates. The AI can only lower confidence; a person approves.
"""
from typing import Literal

from pydantic import BaseModel
from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from ..llm.provider import call_json
from ..models import LEADS, Claim, Conflict, EvidenceUnit

FUZZY_THRESHOLD = 90
MIN_QUOTE_CHARS = 8
_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})


def normalise_with_map(text: str) -> tuple[str, list[int]]:
    """Lowercase, unify quotes/dashes, collapse whitespace; keep a map back to original offsets."""
    out, idx = [], []
    prev_space = True
    for i, ch in enumerate(text.translate(_QUOTES)):
        if ch.isspace():
            if prev_space:
                continue
            out.append(" ")
            idx.append(i)
            prev_space = True
        else:
            out.append(ch.lower())
            idx.append(i)
            prev_space = False
    if out and out[-1] == " ":
        out.pop()
        idx.pop()
    return "".join(out), idx


def _strip(q: str) -> str:
    return q.strip().strip('"').strip("'").strip().rstrip(".").strip("…").strip()


def find_quote(quote: str, text: str) -> tuple[str, float, int | None, int | None]:
    """Return (match kind, score, start, end) with offsets into the original text."""
    q_norm, _ = normalise_with_map(_strip(quote))
    t_norm, idx = normalise_with_map(text)
    if len(q_norm) < MIN_QUOTE_CHARS or not t_norm:
        return "none", 0.0, None, None
    pos = t_norm.find(q_norm)
    if pos >= 0:
        return "exact", 100.0, idx[pos], idx[pos + len(q_norm) - 1] + 1
    al = fuzz.partial_ratio_alignment(q_norm, t_norm, score_cutoff=FUZZY_THRESHOLD)
    if al and al.dest_end > al.dest_start:
        return "fuzzy", round(al.score, 1), idx[al.dest_start], idx[al.dest_end - 1] + 1
    best = fuzz.partial_ratio(q_norm, t_norm)
    return "none", round(best, 1), None, None


def gate1(db: Session, project_id: str, claims: list[Claim]) -> None:
    codes = {c.cited_code for claim in claims for c in claim.citations}
    units = {u.code: u for u in db.query(EvidenceUnit).filter(
        EvidenceUnit.project_id == project_id, EvidenceUnit.code.in_(codes or {""})).all()}
    for claim in claims:
        labels = []
        for cit in claim.citations:
            unit = units.get(cit.cited_code)
            if not unit:
                cit.match, cit.match_score, cit.evidence = "missing_evidence", 0.0, None
                continue
            cit.evidence = unit
            cit.match, cit.match_score, cit.start, cit.end = find_quote(cit.quote, unit.text)
            if cit.match == "exact":
                labels.append(unit.access_label)
        # A claim is as sensitive as the most sensitive evidence that supports it.
        claim.access_label = max(labels) if labels else max(
            [units[c.cited_code].access_label for c in claim.citations if c.cited_code in units] or [1])


def valid_citations(claim: Claim):
    """Only word-for-word quotes count as evidence. Near matches ("fuzzy") are shown but rejected."""
    return [c for c in claim.citations if c.match == "exact"]


def claim_date(claim: Claim) -> str | None:
    """Latest date among the claim's verified evidence (ISO strings sort correctly)."""
    dates = [c.evidence.occurred_at for c in valid_citations(claim) if c.evidence is not None and c.evidence.occurred_at]
    return max(dates) if dates else None


def conflict_members(k: Conflict) -> set[str]:
    return set(k.side_a or []) | set(k.side_b or []) | {k.claim_a_id, k.claim_b_id}


class Verdict(BaseModel):
    claim_ref: str
    verdict: Literal["supports", "partial", "contradicts", "unrelated"]
    reason: str


class SupportResult(BaseModel):
    verdicts: list[Verdict]


SUPPORT_SYSTEM = """You check whether quoted evidence supports a claim. Judge ONLY from the quotes given.
supports: the quotes clearly state the claim, including any status, owner or reason it mentions.
partial: the quotes support part of the claim but some detail (status, owner, reason, timing) is not stated.
contradicts: the quotes say the opposite.
unrelated: the quotes do not address the claim.
A tentative quote ("we might", "maybe", "proposal") does not support a definite claim. Give a short reason."""

SUPPORT_BATCH = 20


def _claim_line(claim: Claim) -> str:
    extras = []
    if claim.status:
        extras.append(f"status={claim.status}")
    if claim.owner:
        extras.append(f"owner={claim.owner}")
    if claim.rationale:
        extras.append(f"reason={claim.rationale}")
    quotes = "\n".join(f'   - [{c.cited_code}] "{c.quote}"' for c in valid_citations(claim))
    extra = f" ({', '.join(extras)})" if extras else ""
    return f"{claim.code} [{claim.type}] {claim.statement}{extra}\n   quotes:\n{quotes}"


def gate2(db: Session, claims: list[Claim]) -> list[str]:
    """Support check for claims that passed gate 1. Returns warnings."""
    todo = [c for c in claims if valid_citations(c)]
    warnings = []
    for i in range(0, len(todo), SUPPORT_BATCH):
        batch = todo[i:i + SUPPORT_BATCH]
        prompt = "Claims to check:\n\n" + "\n\n".join(_claim_line(c) for c in batch)
        result, _ = call_json(db, "support", SUPPORT_SYSTEM, prompt, SupportResult)
        by_ref = {v.claim_ref.strip().upper(): v for v in result.verdicts}
        for c in batch:
            v = by_ref.get(c.code.upper())
            if v:
                c.support, c.support_reason = v.verdict, v.reason[:500]
            else:
                c.support, c.support_reason = None, "Support check returned no verdict for this claim."
                warnings.append(f"No support verdict for {c.code}")
    return warnings


def base_confidence(claim: Claim) -> str:
    if claim.reviewer_note and claim.confidence == "reviewer_asserted":
        return "reviewer_asserted"
    valid = valid_citations(claim)
    if not valid:
        return "leaver_attested" if claim.leaver_evidence_id else "unverified"
    if claim.support in ("contradicts", "unrelated") or claim.support is None:
        return "unverified"
    if claim.support == "partial":
        return "weak"
    sources = {c.evidence.source_id for c in valid if c.evidence is not None}
    return "corroborated" if len(sources) >= 2 else "verified"


def open_conflicts_for(db: Session, claim: Claim, statuses=("open", "kept")) -> list[Conflict]:
    rows = db.query(Conflict).filter(Conflict.project_id == claim.project_id, Conflict.status.in_(statuses)).all()
    return [k for k in rows if claim.id in conflict_members(k)]


def refresh_confidence(db: Session, claim: Claim) -> None:
    if claim.confidence == "reviewer_asserted":
        return
    claim.confidence = "conflicting" if open_conflicts_for(db, claim) else base_confidence(claim)


def label_name(level: int) -> str:
    return {1: "Team", LEADS: "Leads", 3: "Restricted"}.get(level, "Team")
