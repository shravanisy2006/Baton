"""AI quality guardrails: rephrased questions, differently worded topics, output validation."""

import json

import pytest
from conftest import auth, signup

from app.llm.provider import FakeProvider, InvalidAIOutput, call_json, set_providers_for_tests


def _unit(code, text, seq):
    from app.models import EvidenceUnit

    return EvidenceUnit(id=code.lower(), code=code, seq=seq, text=text, source_id="s", kind="paragraph", location={})


def test_retrieval_uses_stems_and_ai_synonyms():
    from app.ask.router import retrieve

    units = [
        _unit("E-1", "Razorpay checkout stays disabled until the sponsor MoU is signed.", 1),
        _unit("E-2", "The venue projector is booked through the AV club.", 2),
        _unit("E-3", "Riya deployed the registration API on Friday.", 3),
    ]
    q = "Why is collecting money from attendees turned off?"
    assert retrieve(units, q) == []  # no shared words: plain matching finds nothing
    hit = retrieve(units, q, extra_terms=["payments", "checkout", "razorpay", "disabled"])
    assert hit and hit[0].code == "E-1"
    # Stemming: "deploys"/"deployed", "registrations"/"registration".
    assert retrieve(units, "Who deploys registrations?")[0].code == "E-3"


def test_ask_answers_a_rephrased_question_and_still_checks_quotes(client):
    rev = signup(client, "Dr. Rao")
    pid = client.post("/projects", json={"name": "Shop app"}, headers=auth(rev)).json()["id"]
    note = b"# Notes\n\nRazorpay checkout stays disabled until the sponsor MoU is signed.\n\nThe projector is booked.\n"
    client.post(
        f"/projects/{pid}/sources/upload", headers=auth(rev), data={"access_label": "Team"}, files=[("files", ("notes.md", note))]
    )
    seen = {}

    def scripted(system, prompt, schema):
        if schema.__name__ == "SearchPlan":
            return json.dumps({"keywords": ["payments", "checkout", "razorpay"]})
        if schema.__name__ == "AskResult":
            seen["prompt"] = prompt
            code = prompt.split("[", 1)[1].split("]", 1)[0]
            return json.dumps(
                {
                    "answerable": True,
                    "answer": "Checkout is off until the MoU is signed.",
                    "citations": [
                        {"evidence_id": code, "quote": "Razorpay checkout stays disabled until the sponsor MoU is signed."}
                    ],
                }
            )
        raise AssertionError(schema.__name__)

    set_providers_for_tests([FakeProvider(scripted)])
    r = client.post(f"/projects/{pid}/ask", headers=auth(rev), json={"question": "Why is collecting money turned off?"})
    assert r.status_code == 200 and r.json()["status"] == "answered", r.text
    assert "Razorpay" in seen["prompt"] and r.json()["citations"][0]["quote"].startswith("Razorpay")


def test_differently_worded_subjects_still_conflict(client):
    rev = signup(client, "Dr. Rao")
    pid = client.post("/projects", json={"name": "Club app"}, headers=auth(rev)).json()["id"]
    files = [
        ("files", ("tasks.md", b"# Tasks\n\nDate: 2026-10-01\n\nThe attendee Excel export is done.\n")),
        (
            "files",
            ("issue.md", b"# Issue\n\nDate: 2026-10-05\n\nReopened: the xlsx download of registrations breaks above 500 rows.\n"),
        ),
    ]
    client.post(f"/projects/{pid}/sources/upload", headers=auth(rev), data={"access_label": "Team"}, files=files)
    grouping = {"groups": []}

    def scripted(system, prompt, schema):
        name = schema.__name__
        if name == "ExtractionResult":
            out = []
            for line in prompt.split("\n\n["):
                code = line.lstrip("[").split("]", 1)[0] if "E-" in line else None
                if code and "Excel export is done" in line:
                    out.append(
                        {
                            "type": "task",
                            "subject": "attendee excel export",
                            "status": "done",
                            "statement": "The attendee Excel export is done.",
                            "citations": [{"evidence_id": code, "quote": "The attendee Excel export is done."}],
                        }
                    )
                if code and "Reopened" in line:
                    out.append(
                        {
                            "type": "task",
                            "subject": "xlsx download of registrations",
                            "status": "reopened",
                            "statement": "The xlsx download of registrations was reopened.",
                            "citations": [
                                {"evidence_id": code, "quote": "the xlsx download of registrations breaks above 500 rows."}
                            ],
                        }
                    )
            return json.dumps({"claims": out})
        if name == "TopicResult":
            return json.dumps(grouping)
        if name == "SupportResult":
            refs = [ln.split(" ", 1)[0] for ln in prompt.splitlines() if ln.startswith("C-")]
            return json.dumps({"verdicts": [{"claim_ref": r, "verdict": "supports", "reason": "ok"} for r in refs]})
        return json.dumps({"verdicts": []})

    set_providers_for_tests([FakeProvider(scripted)])
    client.post(f"/projects/{pid}/analyse", json={}, headers=auth(rev))
    assert client.get(f"/projects/{pid}/conflicts", headers=auth(rev)).json()["conflicts"] == []  # wording differs

    from app.db import SessionLocal
    from app.models import LLMCache

    with SessionLocal() as db:  # the first answer is cached; this test changes what the "AI" says
        db.query(LLMCache).filter_by(task="topics").delete()
        db.commit()
    grouping["groups"] = [
        {
            "topic": "excel export",
            "subjects": ["attendee excel export", "xlsx download of registrations", "a subject the AI made up"],
        }
    ]
    client.post(f"/projects/{pid}/analyse", json={"mode": "full"}, headers=auth(rev))
    conflicts = client.get(f"/projects/{pid}/conflicts", headers=auth(rev)).json()["conflicts"]
    assert len(conflicts) == 1 and conflicts[0]["kind"] == "status" and conflicts[0]["newer_side"] in ("a", "b")


def test_ai_output_is_validated_retried_then_rejected(client):
    from app.db import SessionLocal
    from app.extract.service import ExtractionResult

    calls = {"n": 0}

    def bad_then_good(system, prompt, schema):
        calls["n"] += 1
        return "not json" if calls["n"] == 1 else json.dumps({"claims": []})

    set_providers_for_tests([FakeProvider(bad_then_good)])
    with SessionLocal() as db:
        result, _ = call_json(db, "extract", "sys", "prompt unique 1", ExtractionResult)
    assert result.claims == [] and calls["n"] == 2

    set_providers_for_tests([FakeProvider(lambda s, p, sc: json.dumps({"claims": [{"type": "invented-type"}]}))])
    with SessionLocal() as db, pytest.raises(InvalidAIOutput):
        call_json(db, "extract", "sys", "prompt unique 2", ExtractionResult)
