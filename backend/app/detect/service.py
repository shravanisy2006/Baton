"""Gaps and conflicts: say what is missing or disagreeing instead of guessing.

Rules run on verified claims only, so a hallucinated claim cannot create a fake conflict.
"""
from typing import Literal

from pydantic import BaseModel
from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from ..llm.provider import AIUnavailable, InvalidAIOutput, call_json
from ..models import Claim, Conflict, EvidenceUnit, Gap, Source
from ..verify.service import claim_date, valid_citations

DONE = {"done"}
NOT_DONE = {"todo", "in_progress", "reopened", "blocked"}


def same_subject(a: str, b: str) -> bool:
    a, b = a.strip().lower(), b.strip().lower()
    if not a or not b:
        return False
    return a == b or a in b or b in a or fuzz.token_set_ratio(a, b) >= 85


def _names_match(a: str, b: str) -> bool:
    a, b = a.strip().lower().lstrip("@"), b.strip().lower().lstrip("@")
    return a == b or a in b or b in a or fuzz.ratio(a, b) >= 85


def dedupe(db: Session, claims: list[Claim]) -> list[Claim]:
    """Merge claims stating the same fact so multiple sources corroborate one claim."""
    kept: list[Claim] = []
    for c in claims:
        twin = next((k for k in kept if k.type == c.type and same_subject(k.subject, c.subject)
                     and (k.status or "") == (c.status or "")
                     and (not k.owner or not c.owner or _names_match(k.owner, c.owner))
                     and fuzz.token_set_ratio(k.statement, c.statement) >= 80), None)
        if twin is None:
            kept.append(c)
            continue
        have = {(x.cited_code, x.quote) for x in twin.citations}
        for cit in list(c.citations):
            if (cit.cited_code, cit.quote) not in have:
                c.citations.remove(cit)
                twin.citations.append(cit)
        twin.owner = twin.owner or c.owner
        twin.rationale = twin.rationale or c.rationale
        twin.access_label = max(twin.access_label, c.access_label)
        db.delete(c)
    db.flush()
    return kept


def _source_desc(claim: Claim) -> str:
    v = valid_citations(claim)
    if not v or v[0].evidence is None:
        return "an unverified source"
    ev: EvidenceUnit = v[0].evidence
    d = f", {ev.occurred_at}" if ev.occurred_at else ""
    return f"{ev.source.filename}{d}"


def _same_work(a: Claim, b: Claim) -> bool:
    """Do two claims describe the same piece of work (not just the same topic)?"""
    return fuzz.token_set_ratio(a.statement, b.statement) >= 70 or fuzz.token_set_ratio(
        " ".join(x.quote for x in a.citations), " ".join(x.quote for x in b.citations)) >= 75


def _same_work_loose(c: Claim, anchors: list[Claim]) -> bool:
    """A not-done item that follows up on a reopened/blocked one (e.g. 'the fix isn't started')."""
    return any(fuzz.partial_ratio(c.subject, a.subject) >= 90 for a in anchors)


def _groups(claims: list[Claim]) -> list[list[Claim]]:
    """Group claims about the same subject (transitively), so one topic gives one conflict."""
    groups: list[list[Claim]] = []
    for c in claims:
        hits = [g for g in groups if any(same_subject(c.subject, x.subject) for x in g)]
        merged = [c] + [x for g in hits for x in g]
        groups = [g for g in groups if g not in hits] + [merged]
    return groups


def _side_text(side: list[Claim]) -> str:
    return "; ".join(f"{_source_desc(c)}" for c in side)


def _newer(side_a: list[Claim], side_b: list[Claim]) -> str | None:
    da = max((claim_date(c) or "" for c in side_a), default="")
    db_ = max((claim_date(c) or "" for c in side_b), default="")
    if not da or not db_ or da == db_:
        return None
    return "a" if da > db_ else "b"


def _make(project_id: str, kind: str, side_a: list[Claim], side_b: list[Claim], explanation: str) -> Conflict:
    # Newest claim on each side represents it.
    side_a = sorted(side_a, key=lambda c: claim_date(c) or "", reverse=True)
    side_b = sorted(side_b, key=lambda c: claim_date(c) or "", reverse=True)
    return Conflict(
        project_id=project_id, kind=kind, claim_a_id=side_a[0].id, claim_b_id=side_b[0].id,
        side_a=[c.id for c in side_a], side_b=[c.id for c in side_b], newer_side=_newer(side_a, side_b),
        access_label=max(c.access_label for c in side_a + side_b), explanation=explanation,
    )


def detect_conflicts(db: Session, project_id: str, claims: list[Claim]) -> list[Conflict]:
    usable = [c for c in claims if valid_citations(c) and c.support in ("supports", "partial")]
    found: list[Conflict] = []

    # Status: within one topic, "done" vs "not done" about the SAME piece of work -> ONE conflict.
    # Different tasks that merely share a topic ("add the flag" done, "turn the flag on" to do) are not a
    # conflict, and a newer "done" after an older "to do" is ordinary progress.
    tasks = [c for c in usable if c.type in ("task", "blocker") and c.status]
    for g in _groups(tasks):
        done = [c for c in g if c.status in DONE]
        not_done = [c for c in g if c.status in NOT_DONE]
        if not done or not not_done:
            continue
        explicit = [c for c in not_done if c.status in ("reopened", "blocked")]
        latest_done = max((claim_date(c) or "" for c in done), default="")
        same_work = [c for c in not_done if c in explicit or any(_same_work(c, d) for d in done)]
        newer_not_done = [c for c in same_work if c in explicit or (claim_date(c) or "") >= latest_done]
        if not explicit and not newer_not_done:
            continue  # unrelated tasks on one topic, or progress (done is the newest word)
        if explicit:
            not_done = [c for c in not_done if c in explicit or any(_same_work(c, x) for x in explicit + done)
                        or _same_work_loose(c, explicit)]
        else:
            not_done = newer_not_done
        done = [d for d in done if any(_same_work(d, c) for c in not_done) or explicit]
        if done and not_done:
            k = _make(project_id, "status", done, not_done, "")
            newer = {"a": "done", "b": "not done"}.get(k.newer_side or "", None)
            states = sorted({c.status.replace("_", " ") for c in not_done})
            k.explanation = (
                f"Status of '{g[0].subject}' disagrees. Says done: {_side_text(done)}. "
                f"Says {' / '.join(states)}: {_side_text(not_done)}."
                + (f" The newer evidence says {newer}." if newer else "")
            )
            found.append(k)

    # Owner: within one topic, the SAME piece of work with two or more different owners -> ONE conflict.
    owned = [c for c in usable if c.type in ("task", "owner") and c.owner]
    for g in _groups(owned):
        clusters: list[list[Claim]] = []
        for c in g:
            home = next((cl for cl in clusters if _names_match(cl[0].owner, c.owner)), None)
            (home.append(c) if home else clusters.append([c]))
        clashing = len(clusters) >= 2 and any(
            _same_work(a, b) for i, x in enumerate(clusters) for y in clusters[i + 1:] for a in x for b in y)
        if clashing:
            a, b = clusters[0], [c for cl in clusters[1:] for c in cl]
            found.append(_make(project_id, "owner", a, b,
                               f"Different owners for '{g[0].subject}': "
                               + "; ".join(f"{cl[0].owner} ({_side_text(cl)})" for cl in clusters) + "."))
    for c in found:
        db.add(c)
    db.flush()
    return found


class PairVerdict(BaseModel):
    pair_ref: str
    verdict: Literal["replaces", "compatible", "unclear"]
    reason: str


class SupersedeResult(BaseModel):
    verdicts: list[PairVerdict]


SUPERSEDE_SYSTEM = """You check whether a NEWER project decision or instruction replaces or reverses an OLDER decision
about the same topic.
replaces: the newer item changes, reverses or ends the older decision (including when the older decision's condition
has now been met and the newer item acts on that), so someone following only the older decision would now do the wrong thing.
compatible: both can be true at the same time (one adds detail, implements or repeats the other).
unclear: the quotes don't let you tell. Judge only from the quotes given. Give a short reason."""


def detect_supersessions(db: Session, project_id: str, claims: list[Claim]) -> tuple[list[Conflict], list[str]]:
    """Timeline check: flag an older decision that a newer decision or instruction on the same topic may
    have replaced (e.g. "keep payments off until the MoU" -> later "turn payments back on on 20 Nov")."""
    dated = [c for c in claims if valid_citations(c) and c.support in ("supports", "partial") and claim_date(c)]
    decisions = [c for c in dated if c.type == "decision"]
    later_items = [c for c in dated if c.type in ("decision", "task")]
    pairs: list[tuple[Claim, Claim]] = []
    seen: set[tuple[str, str]] = set()
    for older in decisions:
        for newer in later_items:
            if newer is older or claim_date(newer) <= claim_date(older):
                continue
            if not same_subject(older.subject, newer.subject):
                continue
            if fuzz.token_set_ratio(older.statement, newer.statement) >= 80:
                continue  # same decision restated
            if (older.id, newer.id) not in seen:
                seen.add((older.id, newer.id))
                pairs.append((older, newer))
    if not pairs:
        return [], []

    def quote(c: Claim) -> str:
        return " / ".join(f'"{x.quote}"' for x in valid_citations(c))

    prompt = "Decision pairs:\n\n" + "\n\n".join(
        f"P{n} OLDER ({claim_date(o)}): {o.statement} -- quotes: {quote(o)}\n"
        f"   NEWER ({claim_date(w)}): {w.statement} -- quotes: {quote(w)}"
        for n, (o, w) in enumerate(pairs, start=1))
    try:
        result, _ = call_json(db, "supersede", SUPERSEDE_SYSTEM, prompt, SupersedeResult)
    except (AIUnavailable, InvalidAIOutput) as e:
        return [], [f"Timeline (supersession) check skipped: {e}"]
    verdicts = {v.pair_ref.strip().upper(): v for v in result.verdicts}
    replaced = [(o, w, verdicts[f"P{n}"].reason) for n, (o, w) in enumerate(pairs, start=1)
                if verdicts.get(f"P{n}") and verdicts[f"P{n}"].verdict == "replaces"]
    # One timeline conflict per topic: every replaced older decision vs every newer item that replaces it.
    found = []
    for group in _groups(list({c.id: c for o, w, _ in replaced for c in (o, w)}.values())):
        ids = {c.id for c in group}
        rows = [(o, w, r) for o, w, r in replaced if o.id in ids]
        olds = list({o.id: o for o, _, _ in rows}.values())
        news = [w for w in {w.id: w for _, w, _ in rows}.values() if w.id not in {o.id for o in olds}]
        if not olds or not news:
            continue
        k = _make(project_id, "superseded", olds, news,
                  f"Newer evidence on '{olds[0].subject}' ({_side_text(news)}) may replace an older decision "
                  f"({_side_text(olds)}). Why: {rows[0][2]}")
        k.newer_side = "b"
        found.append(k)
        db.add(k)
    db.flush()
    return found, []


def detect_gaps(db: Session, project_id: str, claims: list[Claim], conflicts: list[Conflict]) -> list[Gap]:
    gaps: list[Gap] = []
    usable = [c for c in claims if valid_citations(c)]
    asked_owner: list[str] = []  # one "who owns X?" question per topic
    for c in usable:
        if c.type == "task" and c.status != "done" and not c.owner:
            if any(same_subject(c.subject, s) for s in asked_owner):
                continue
            asked_owner.append(c.subject)
            gaps.append(Gap(project_id=project_id, claim_id=c.id, kind="missing_owner", access_label=c.access_label,
                            question=f"Who owns \"{c.subject}\" now? The sources don't name an owner."))
        elif c.type == "decision" and not c.rationale and not any(
                o is not c and o.type == "decision" and o.rationale and same_subject(o.subject, c.subject)
                for o in usable):
            gaps.append(Gap(project_id=project_id, claim_id=c.id, kind="missing_reason", access_label=c.access_label,
                            question=f"Why was this decided: \"{c.statement}\"?"))
        elif c.type == "open_question":
            gaps.append(Gap(project_id=project_id, claim_id=c.id, kind="open_question", access_label=c.access_label,
                            question=f"Is this still open: \"{c.statement}\" If it was answered, what was decided?"))
    by_id = {c.id: c for c in claims}
    for k in conflicts:
        a = by_id.get(k.claim_a_id)
        subject = a.subject if a else "this item"
        ask = "Which is current?" if k.kind != "superseded" else "Does the newer decision replace the older one?"
        gaps.append(Gap(project_id=project_id, claim_id=None, conflict_id=k.id, kind="conflict",
                        access_label=k.access_label,
                        question=f"Sources disagree about \"{subject}\". {k.explanation} {ask}"))
    for s in db.query(Source).filter_by(project_id=project_id).filter(Source.status.in_(("unreadable", "failed"))):
        gaps.append(Gap(project_id=project_id, source_id=s.id, kind="unreadable_source", access_label=s.access_label,
                        question=f"\"{s.filename}\" could not be read. Is there anything in it the new member must know?"))
    for g in gaps:
        db.add(g)
    db.flush()
    return gaps
