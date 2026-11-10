"""Build the handover from approved claims only. Every item carries its evidence references."""
from sqlalchemy.orm import Session

from ..detect.service import _names_match
from ..models import APPROVED_STATES, LABELS, Claim, Gap, Project, User
from ..verify.service import valid_citations

SECTIONS = [
    ("own", "What you own"),
    ("next", "Next actions"),
    ("unfinished", "Unfinished work"),
    ("decisions", "Important decisions and why"),
    ("risks", "Risks and things not to break"),
    ("dependencies", "Dependencies and blockers"),
    ("questions", "Open questions"),
    ("contacts", "Important contacts"),
]


def _aliases(u: User | None) -> list[str]:
    if not u:
        return []
    names = [u.name, u.name.split()[0]]
    if u.handle:
        names.append(u.handle)
    return [n for n in names if n]


def _owned_by(owner: str | None, people: list[str]) -> bool:
    return bool(owner) and any(_names_match(owner, p) for p in people)


def _item(c: Claim) -> dict:
    evidence = []
    for cit in valid_citations(c):
        ev = cit.evidence
        evidence.append({
            "evidence_id": ev.id, "code": ev.code, "source": ev.source.filename, "kind": ev.kind,
            "source_type": ev.source.kind, "match": cit.match,
            "author": ev.author, "date": ev.occurred_at, "location": ev.location, "quote": cit.quote,
            "start": cit.start, "end": cit.end, "access_level": ev.access_label, "url": ev.location.get("url"),
        })
    return {
        "claim_id": c.id, "code": c.code, "type": c.type, "subject": c.subject, "text": c.statement,
        "review_state": c.review_state,
        "status": c.status, "owner": c.owner, "owner_reassigned": c.owner_reassigned, "rationale": c.rationale,
        "confidence": c.confidence, "leaver_note": c.leaver_note, "reviewer_note": c.reviewer_note,
        "leaver_evidence_id": c.leaver_evidence_id, "access_level": c.access_label, "evidence": evidence,
    }


def build_snapshot(db: Session, project: Project) -> dict:
    departing = db.get(User, project.departing_user_id) if project.departing_user_id else None
    incoming = db.get(User, project.incoming_user_id) if project.incoming_user_id else None
    leaver_names, new_names = _aliases(departing), _aliases(incoming)
    claims = db.query(Claim).filter(Claim.project_id == project.id, Claim.review_state.in_(APPROVED_STATES)).all()
    claims.sort(key=lambda c: int(c.code.split("-")[1]))
    sections: dict[str, list] = {k: [] for k, _ in SECTIONS}
    for c in claims:
        item = _item(c)
        owned = _owned_by(c.owner, leaver_names) or (c.owner_reassigned and _owned_by(c.owner, new_names))
        if c.type in ("task", "owner") and owned and c.status != "done":
            sections["own"].append(item)
        elif c.type == "owner" and owned:
            sections["own"].append(item)
        elif c.type == "task":
            if c.status == "done":
                continue  # finished work is not handed over
            sections["unfinished"].append(item)
        elif c.type == "decision":
            sections["decisions"].append(item)
        elif c.type in ("risk", "recurring_problem"):
            sections["risks"].append(item)
        elif c.type in ("dependency", "blocker"):
            sections["dependencies"].append(item)
        elif c.type == "open_question":
            sections["questions"].append(item)
        elif c.type == "contact":
            sections["contacts"].append(item)
        elif c.type == "owner":
            sections["unfinished"].append(item)
    # Next actions: every open task or blocker, most urgent first, with a plain instruction.
    urgency = {"reopened": 0, "blocked": 1, "in_progress": 2, "todo": 3, "unknown": 4, None: 5}
    open_work = [i for i in sections["own"] + sections["unfinished"] + sections["dependencies"]
                 if i["type"] in ("task", "blocker") and i.get("status") != "done"]
    for i in sorted(open_work, key=lambda i: urgency.get(i.get("status"), 5)):
        verb = {"reopened": "Fix and re-test", "blocked": "Unblock", "in_progress": "Finish",
                "todo": "Start"}.get(i.get("status") or "", "Check the status of")
        if i["type"] == "blocker":
            verb = "Unblock"
        action = f"{verb}: {i['text']}"
        if not i.get("owner"):
            action += " (no owner yet: assign one)"
        sections["next"].append({**i, "action": action})

    # Unanswered gaps are shown honestly as unknowns, never filled in. A gap about an approved claim is
    # attached to that claim's line; other open gaps get their own line under open questions.
    by_claim: dict[str, list[dict]] = {}
    for sec in sections.values():
        for i in sec:
            by_claim.setdefault(i["claim_id"], []).append(i)
    for g in db.query(Gap).filter_by(project_id=project.id, status="open").all():
        if g.kind == "unreadable_source":
            continue
        if g.claim_id:
            for item in by_claim.get(g.claim_id, []):
                item["open_gap"] = g.question
            continue
        sections["questions"].append({
            "claim_id": None, "code": None, "type": "gap", "text": g.question, "confidence": "unknown",
            "access_level": g.access_label, "evidence": [], "gap_kind": g.kind,
        })
    return {
        "project": project.name,
        "departing": departing.name if departing else None,
        "incoming": incoming.name if incoming else None,
        "sections": [{"key": k, "title": t, "items": sections[k],
                      "note": (f"Work {departing.name} owned, which now passes to you." if k == "own" and departing else None)}
                     for k, t in SECTIONS],
    }


def filter_for_level(snapshot: dict, level: int) -> dict:
    """Re-check permissions at read time: drop items above the reader's level, count what was hidden."""
    out = dict(snapshot)
    out_sections, hidden_total = [], 0
    for sec in snapshot.get("sections", []):
        visible, hidden = [], 0
        for item in sec["items"]:
            if item["access_level"] > level:
                hidden += 1
                continue
            item = dict(item)
            item["evidence"] = [e for e in item["evidence"] if e["access_level"] <= level]
            item["access_label"] = LABELS.get(item["access_level"], "Team")
            visible.append(item)
        hidden_total += hidden
        out_sections.append({**sec, "items": visible, "hidden_count": hidden})
    out["sections"] = out_sections
    out["hidden_count"] = hidden_total
    return out
