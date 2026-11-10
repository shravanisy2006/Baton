"""Claim extraction: evidence units in, typed claims with cited quotes out.

The AI never sees evidence the pipeline isn't allowed to use, and it must cite evidence IDs plus an
exact quote for every claim. Nothing is trusted yet: the verify module checks every citation.
"""
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..llm.provider import call_json
from ..models import Claim, ClaimEvidence, EvidenceUnit

ClaimType = Literal["decision", "task", "owner", "blocker", "dependency", "risk",
                    "open_question", "recurring_problem", "contact"]
TaskStatus = Literal["todo", "in_progress", "done", "blocked", "reopened", "unknown"]


class Citation(BaseModel):
    evidence_id: str = Field(description="Evidence ID exactly as shown, e.g. E-3")
    quote: str = Field(description="Exact words copied from that evidence, 4 to 30 words")


class ExtractedClaim(BaseModel):
    type: ClaimType
    subject: str = Field(description="Short lowercase name of the thing this is about, e.g. 'excel export'")
    statement: str = Field(description="One plain sentence stating the fact")
    status: TaskStatus | None = None
    owner: str | None = None
    rationale: str | None = None
    citations: list[Citation] = Field(min_length=1)

    @field_validator("statement", "subject")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v.strip()


class ExtractionResult(BaseModel):
    claims: list[ExtractedClaim]


SYSTEM = """You help hand over a software project when a team member leaves.
From the numbered evidence, extract the facts a new team member needs: decisions (and the reason given),
tasks and their status, who owns what, blockers, dependencies, risks, open questions, recurring problems
and important contacts.

Strict rules:
1. Use ONLY the evidence given. Never add outside knowledge or guesses.
2. Every claim must cite at least one evidence ID exactly as written (e.g. "E-3") and a quote copied
   word for word from that same evidence item (4 to 30 words). Do not paraphrase quotes.
3. If the same fact appears in several evidence items, put it in ONE claim and cite all of them.
4. If two evidence items disagree (for example a task marked Done in one and broken or reopened in
   another), extract them as SEPARATE claims with the same subject. Do not resolve the disagreement.
5. subject: a short lowercase noun phrase for the thing the claim is about. Use the same subject for
   every claim about the same thing (e.g. "excel export", "payments", "sponsor mou").
6. status: only for task and blocker claims: todo, in_progress, done, blocked, reopened or unknown.
7. owner: the person or handle named in the evidence as responsible, else null. Never invent an owner.
8. rationale: for decisions, the reason stated in the evidence, else null.
9. Skip greetings, chit-chat and anything not useful for continuing the work."""

MAX_BATCH_CHARS = 12000


def _format_unit(u: EvidenceUnit, filename: str) -> str:
    meta = [f"source: {filename}"]
    if u.author:
        meta.append(f"author: {u.author}")
    if u.occurred_at:
        meta.append(f"date: {u.occurred_at}")
    if u.location.get("section"):
        meta.append(f"section: {u.location['section']}")
    return f"[{u.code}] ({' | '.join(meta)})\n{u.text}"


def make_batches(units: list[EvidenceUnit], filenames: dict[str, str]) -> list[list[EvidenceUnit]]:
    batches, cur, size = [], [], 0
    for u in units:
        block = len(u.text) + 80
        if cur and size + block > MAX_BATCH_CHARS:
            batches.append(cur)
            cur, size = [], 0
        cur.append(u)
        size += block
    if cur:
        batches.append(cur)
    return batches


def next_claim_no(db: Session, project_id: str) -> int:
    n = db.query(func.count(Claim.id)).filter_by(project_id=project_id).scalar() or 0
    return n + 1


def extract_batch(db: Session, project_id: str, batch: list[EvidenceUnit], filenames: dict[str, str]) -> list[Claim]:
    prompt = "Evidence:\n\n" + "\n\n".join(_format_unit(u, filenames[u.source_id]) for u in batch)
    result, provider = call_json(db, "extract", SYSTEM, prompt, ExtractionResult)
    n = next_claim_no(db, project_id)
    created = []
    for ec in result.claims:
        claim = Claim(
            project_id=project_id, code=f"C-{n}", type=ec.type, subject=ec.subject.lower()[:200],
            statement=ec.statement, original_statement=ec.statement,
            status=ec.status if ec.type in ("task", "blocker") else None,
            owner=(ec.owner or None), rationale=(ec.rationale or None),
            extractor=provider,
        )
        for c in ec.citations:
            claim.citations.append(ClaimEvidence(cited_code=c.evidence_id.strip().upper(), quote=c.quote.strip()))
        db.add(claim)
        created.append(claim)
        n += 1
    db.flush()
    return created
