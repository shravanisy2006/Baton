"""Ask Baton: plain questions answered only from evidence the asker is allowed to see.

1. Retrieval runs in code over evidence units at or below the asker's access level (including earlier
   answers from the leaver), so the AI never sees anything the asker can't.
2. The AI drafts a short answer and must cite evidence IDs with exact quotes.
3. Every quote goes through the same word-for-word check as claims. Quotes that fail are dropped; if no quote
   survives, Baton says it can't answer from the evidence instead of guessing.
4. An unanswered question can be sent to the leaver (or reviewer) as a new gap; their answer is saved as
   labelled evidence, so the next person who asks gets it with a citation.
"""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from ..audit.service import log as audit
from ..auth.security import CAN_REVIEW, current_session, require_member
from ..db import get_db
from ..ingest.redact import redact
from ..llm.provider import AIUnavailable, InvalidAIOutput, call_json
from ..models import LABELS, EvidenceUnit, Gap, Question, Source
from ..verify.service import find_quote

router = APIRouter(tags=["ask"])
TOP_K = 12
STOP = set("""a an the is are was were be been to of in on for and or but with at by from it this that these those
what which who whom whose why how when where do does did can could should would will shall may might must i we you
he she they me us our your my their there here about into than then so if not no yes any some all
please tell know""".split())


class Cite(BaseModel):
    evidence_id: str = Field(description="The evidence ID in square brackets, e.g. E-12")
    quote: str = Field(description="Exact words copied from that evidence")


class AskResult(BaseModel):
    answerable: bool
    answer: str = ""
    citations: list[Cite] = Field(default_factory=list)


SYSTEM = """You answer a new team member's question about a project, using ONLY the numbered evidence given.
Rules:
1. If the evidence does not clearly answer the question, set answerable=false and leave answer empty. Never guess,
   never use outside knowledge.
2. If it does, write a short, direct answer (1-4 sentences) and cite every fact: give the evidence ID and an EXACT
   quote copied word for word from that evidence (one sentence or less). Quotes that are not word for word will be
   rejected.
3. If evidence disagrees or something was later changed, say so and prefer the newest dated evidence, citing both.
4. Evidence marked attestation is a person's own answer; you may use it and must cite it like any other."""


def _terms(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9_]+", text.lower()) if w not in STOP and len(w) > 1]


def retrieve(units: list[EvidenceUnit], question: str, k: int = TOP_K) -> list[EvidenceUnit]:
    terms = set(_terms(question))
    if not terms:
        return []
    scored = []
    for u in units:
        words = set(_terms(u.text))
        overlap = len(terms & words) + 0.5 * sum(1 for t in terms if any(w.startswith(t[:5]) for w in words if len(t) >= 5))
        if overlap == 0:
            continue
        score = overlap * 10 + fuzz.token_set_ratio(question, u.text) / 10
        scored.append((score, u))
    scored.sort(key=lambda x: (-x[0], x[1].seq))
    return [u for _, u in scored[:k]]


def _format(u: EvidenceUnit, filename: str) -> str:
    meta = [filename]
    if u.author:
        meta.append(f"by {u.author}")
    if u.occurred_at:
        meta.append(u.occurred_at)
    if u.kind == "attestation":
        meta.append("attestation")
    return f"[{u.code}] ({' | '.join(meta)})\n{u.text}"


def question_out(q: Question) -> dict:
    return {"id": q.id, "question": q.question, "status": q.status, "answer": q.answer,
            "citations": q.citations or [], "rejected_quotes": q.rejected_quotes,
            "asked_by": q.asked_by_name, "person_answer": q.person_answer, "person_answer_by": q.person_answer_by,
            "sent": bool(q.gap_id), "created_at": q.created_at.isoformat(), "model": q.model}


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@router.post("/projects/{project_id}/ask")
def ask(project_id: str, body: AskIn, s=Depends(current_session), db: Session = Depends(get_db)):
    m = require_member(db, project_id, s)
    question = " ".join(body.question.split())
    if len(_terms(question)) == 0:
        raise HTTPException(422, "Ask a question with a few key words, e.g. \"Why are online payments switched off?\"")
    units = db.query(EvidenceUnit).filter(EvidenceUnit.project_id == project_id,
                                          EvidenceUnit.access_label <= m.level).all()
    if not units:
        raise HTTPException(409, "There is no evidence in this project yet.")
    filenames = {x.id: x.filename for x in db.query(Source).filter_by(project_id=project_id)}
    top = retrieve(units, question)
    q = Question(project_id=project_id, asked_by=m.user.id, asked_by_name=m.user.name, access_level=m.level,
                 question=question, status="unanswered")
    if top:
        prompt = (f"Question: {question}\n\nEvidence:\n\n"
                  + "\n\n".join(_format(u, filenames.get(u.source_id, "")) for u in top))
        try:
            result, model = call_json(db, "ask", SYSTEM, prompt, AskResult)
        except (AIUnavailable, InvalidAIOutput) as e:
            raise HTTPException(503, f"The AI is busy right now, so Baton can't answer. Try again in a minute. ({str(e)[:120]})") from e
        q.model = model
        allowed = {u.code: u for u in top}
        good, rejected = [], 0
        for c in result.citations if result.answerable else []:
            u = allowed.get(c.evidence_id.strip().upper())
            if not u:
                rejected += 1
                continue
            kind, _, start, end = find_quote(c.quote, u.text)
            if kind != "exact":
                rejected += 1
                continue
            src = filenames.get(u.source_id, "")
            if any(g["code"] == u.code and g["start"] == start for g in good):
                continue
            good.append({"evidence_id": u.id, "code": u.code, "quote": c.quote.strip(), "source": src,
                         "author": u.author, "date": u.occurred_at, "start": start, "end": end, "text": u.text,
                         "location": u.location, "kind": u.kind, "match": "exact",
                         "access_label": LABELS[u.access_label]})
        q.rejected_quotes = rejected
        if result.answerable and good and result.answer.strip():
            q.status, q.answer, q.citations = "answered", result.answer.strip()[:1500], good
    db.add(q)
    db.flush()
    audit(db, project_id, m.user, "question.asked", "question", q.id, status=q.status,
          citations=len(q.citations or []), rejected_quotes=q.rejected_quotes)
    db.commit()
    return question_out(q)


@router.get("/projects/{project_id}/questions")
def list_questions(project_id: str, s=Depends(current_session), db: Session = Depends(get_db)):
    """Your own questions; reviewers and the leaver also see everyone's (filtered by their level)."""
    m = require_member(db, project_id, s)
    rows = db.query(Question).filter_by(project_id=project_id)
    if m.role in ("incoming", "viewer"):
        rows = rows.filter_by(asked_by=m.user.id)
    else:
        rows = rows.filter(Question.access_level <= m.level)
    return {"questions": [question_out(q) for q in rows.order_by(Question.created_at.desc()).limit(100)]}


@router.post("/questions/{question_id}/send")
def send_to_person(question_id: str, s=Depends(current_session), db: Session = Depends(get_db)):
    """Ask a person: the question becomes a gap for the leaver (or reviewer) to answer."""
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(404, "Question not found.")
    m = require_member(db, q.project_id, s)
    if q.asked_by != m.user.id and m.role not in CAN_REVIEW:
        raise HTTPException(404, "Question not found.")
    if q.gap_id:
        return question_out(q)
    text, _ = redact(q.question)
    g = Gap(project_id=q.project_id, kind="asked", access_label=q.access_level,
            question=f"{q.asked_by_name} asked: \"{text}\" The project's files don't answer this.")
    db.add(g)
    db.flush()
    q.gap_id, q.status = g.id, ("sent" if q.status != "answered" else q.status)
    audit(db, q.project_id, m.user, "question.sent_to_person", "question", q.id, gap=g.id)
    db.commit()
    return question_out(q)
