import json
import os
import re
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="baton-test-")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_tmp}/test.db"
os.environ["LOCAL_STORAGE_DIR"] = f"{_tmp}/storage"
os.environ["GEMINI_API_KEY"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.llm.provider import FakeProvider, set_providers_for_tests  # noqa: E402
from app.main import app  # noqa: E402

UNIT_RE = re.compile(r"^\[(E-\d+)\] \((.*?)\)\n(.*?)(?=\n\n\[E-\d+\] |\Z)", re.S | re.M)


def _units(prompt: str) -> dict[str, str]:
    return {m.group(1): m.group(3) for m in UNIT_RE.finditer(prompt)}


def _find(units: dict[str, str], phrase: str) -> str | None:
    return next((code for code, text in units.items() if phrase.lower() in text.lower()), None)


def fake_extract(prompt: str) -> dict:
    """Scripted stand-in for Gemini on the EventApp demo, including deliberate mistakes."""
    u = _units(prompt)
    claims = []

    def add(phrase, **claim):
        code = _find(u, phrase)
        if code:
            claim["citations"] = [{"evidence_id": code, "quote": claim.pop("quote", phrase)}] + claim.pop("extra", [])
            claims.append(claim)

    pr = _find(u, "Dropping Razorpay")
    add("keep online payments disabled with the PAYMENTS_ENABLED flag", type="decision", subject="payments",
        statement="Online payments stay disabled with PAYMENTS_ENABLED until the sponsor MoU is signed.",
        rationale="The sponsor asked to pause payments until the MoU is signed.",
        extra=[{"evidence_id": pr, "quote": "The sponsor asked us to pause payments until the MoU is signed."}] if pr else [])
    add("Task: Export attendees to Excel | Assignee: riya-dev | Status: Done", type="task", subject="excel export",
        statement="The attendee Excel export is done.", status="done", owner="riya-dev")
    add("above 500 rows it times out and the downloaded file is corrupted", type="task", subject="excel export",
        statement="The attendee Excel export is broken above 500 rows and was reopened.", status="reopened")
    add("follow up with the sponsor about when the MoU will be signed", type="task", subject="sponsor mou follow-up",
        statement="Someone must follow up with the sponsor about the MoU signing date.", status="todo")
    add("do we support offline check-in at the venue", type="open_question", subject="offline check-in",
        statement="It is undecided whether offline check-in at the venue is supported.")
    add("Do not change the registrations table schema before the fest", type="risk", subject="registrations schema",
        statement="Do not change the registrations table schema before the fest; the check-in app reads it.")
    add("Riya owns the registration API and the deploy scripts", type="owner", subject="deploy scripts",
        statement="Riya owns the registration API and the deploy scripts.", owner="Riya")
    add("the CI build fails every Monday because the test API token expires weekly", type="recurring_problem",
        subject="ci token", statement="CI fails every Monday because the test API token expires weekly.")
    add("depends on the /v2/attendees endpoint", type="dependency", subject="v2 attendees endpoint",
        statement="The mobile check-in app depends on the /v2/attendees endpoint.")
    add("Our sponsor contact for the MoU is Arjun Rao", type="contact", subject="sponsor contact",
        statement="Arjun Rao is the sponsor contact for the MoU.")
    # More sources on both sides of the Excel export disagreement (must become ONE conflict):
    add("The attendee Excel export was marked Done last week", type="task", subject="excel export",
        statement="The attendee Excel export was marked Done last week.", status="done", owner="Riya")
    add("I have not started the fix yet", type="task", subject="excel export",
        statement="The chunked-writes fix for the Excel export has not been started.", status="todo")
    # A newer decision that reverses the older payments decision (timeline check):
    add("we will switch online payments back on after the fest", type="task", subject="payments",
        statement="Online payments will be switched back on after the fest because the MoU is signed.",
        status="todo", owner="Karan")
    add("Add PAYMENTS_ENABLED flag (default false)", type="task", subject="payments flag",
        statement="Add the PAYMENTS_ENABLED flag with default false and hide the checkout button.", status="done",
        owner="riya-dev")
    add("I'll turn the flag on on 20 November after testing checkout", type="task", subject="payments flag",
        statement="Karan will turn PAYMENTS_ENABLED on on 20 November after testing checkout.",
        status="todo", owner="Karan")
    # A quote with altered words: must be rejected by the word-for-word check.
    meeting2 = _find(u, "Riya owns the registration API")
    if meeting2:
        claims.append({"type": "owner", "subject": "registration api", "statement": "Riya owns the registration API.",
                       "owner": "Riya", "citations": [{"evidence_id": meeting2,
                                                       "quote": "Riya owns the registration API and all deploy scripts"}]})
    # Deliberate mistakes the verifier must catch:
    meeting = _find(u, "Online payments are paused")
    if meeting:
        claims.append({"type": "decision", "subject": "payments resume", "statement": "Payments will resume in November.",
                       "citations": [{"evidence_id": meeting, "quote": "payments will resume in November"}]})
        claims.append({"type": "risk", "subject": "registration api tests",
                       "statement": "The registration API has no automated tests.",
                       "citations": [{"evidence_id": meeting, "quote": "Online payments are paused because the sponsor"}]})
        claims.append({"type": "task", "subject": "analytics", "statement": "Build an analytics page.", "status": "todo",
                       "citations": [{"evidence_id": "E-999", "quote": "build an analytics page for sponsors"}]})
    return {"claims": claims}


def fake_support(prompt: str) -> dict:
    verdicts = []
    for m in re.finditer(r"^(C-\d+) \[(\w+)\] (.*?)$", prompt, re.M):
        code, statement = m.group(1), m.group(3)
        verdict = "unrelated" if "no automated tests" in statement else "supports"
        verdicts.append({"claim_ref": code, "verdict": verdict, "reason": "scripted test verdict"})
    return {"verdicts": verdicts}


def fake_supersede(prompt: str) -> dict:
    verdicts = []
    for m in re.finditer(r"^(P\d+) OLDER.*?\n\s+NEWER.*?: (.*?) -- ", prompt, re.M):
        verdict = "replaces" if ("switched back on" in m.group(2) or "turn PAYMENTS_ENABLED on" in m.group(2)) else "compatible"
        verdicts.append({"pair_ref": m.group(1), "verdict": verdict, "reason": "scripted test verdict"})
    return {"verdicts": verdicts}


def fake_llm(system: str, prompt: str, schema) -> str:
    if schema.__name__ == "ExtractionResult":
        return json.dumps(fake_extract(prompt))
    if schema.__name__ == "SupersedeResult":
        return json.dumps(fake_supersede(prompt))
    return json.dumps(fake_support(prompt))


@pytest.fixture(autouse=True)
def fake_ai():
    set_providers_for_tests([FakeProvider(fake_llm)])
    yield
    set_providers_for_tests(None)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def demo(client):
    r = client.post("/auth/demo")
    assert r.status_code == 200, r.text
    data = r.json()
    people = {p["name"]: p["id"] for p in client.get("/auth/me", headers=auth(data["token"])).json()["people"]}
    tokens = {}
    for name, uid in people.items():
        tokens[name] = client.post("/auth/act-as", json={"user_id": uid}, headers=auth(data["token"])).json()["token"]
    return {"project_id": data["project_id"], "tokens": tokens, "people": people}
