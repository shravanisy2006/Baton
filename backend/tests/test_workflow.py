"""End-to-end tests for the evidence-to-handover workflow (the TESTING.md scenarios)."""
import io

from docx import Document

from app.verify.service import find_quote
from conftest import auth, signup

REVIEWER, LEAVER, NEW, VIEWER = "Priya Nair", "Riya Sharma", "Karan Mehta", "Anika Joshi"


def claims_of(client, demo, who=REVIEWER):
    r = client.get(f"/projects/{demo['project_id']}/claims", headers=auth(demo["tokens"][who]))
    assert r.status_code == 200, r.text
    return r.json()


def by_statement(claims, text):
    return next(c for c in claims["claims"] if text.lower() in c["statement"].lower())


# ---------- 1-3: parsing ----------

def test_upload_pdf_docx_csv_and_reject_unsupported(client):
    tok = signup(client)
    pid = client.post("/projects", json={"name": "Parsing test"}, headers=auth(tok)).json()["id"]
    doc = Document()
    doc.add_heading("Design notes", 1)
    doc.add_paragraph("We chose Supabase because it gives auth and Postgres in one place.")
    buf = io.BytesIO()
    doc.save(buf)
    from reportlab.pdfgen import canvas
    pdf = io.BytesIO()
    c = canvas.Canvas(pdf)
    c.drawString(72, 720, "The deploy script must only run from the main branch.")
    c.save()
    files = [
        ("files", ("notes.docx", buf.getvalue(), "application/octet-stream")),
        ("files", ("runbook.pdf", pdf.getvalue(), "application/pdf")),
        ("files", ("tasks.csv", b"Task,Owner,Status\nFix login bug,asha,Done\nAdd dark mode,,To do\n", "text/csv")),
        ("files", ("photo.png", b"\x89PNG....", "image/png")),
        ("files", ("empty.csv", b"Task,Owner\n", "text/csv")),
    ]
    r = client.post(f"/projects/{pid}/sources/upload", files=files, data={"access_label": "Team"}, headers=auth(tok))
    assert r.status_code == 200, r.text
    res = {x["filename"]: x for x in r.json()["results"]}
    assert res["notes.docx"]["ok"] and res["notes.docx"]["source"]["unit_count"] >= 1
    assert res["runbook.pdf"]["ok"] and res["runbook.pdf"]["source"]["unit_count"] == 1
    assert res["tasks.csv"]["source"]["unit_count"] == 2
    assert not res["photo.png"]["ok"] and "Unsupported" in res["photo.png"]["error"]
    assert not res["empty.csv"]["ok"] and res["empty.csv"]["source"]["status"] == "failed"
    ev = client.get(f"/projects/{pid}/evidence", headers=auth(tok)).json()["evidence"]
    row = next(e for e in ev if e["kind"] == "csv_row" and "Fix login bug" in e["text"])
    assert row["location"] == {"row": 1} and row["code"].startswith("E-")


def test_redaction_removes_secrets(client):
    tok = signup(client)
    pid = client.post("/projects", json={"name": "Secrets"}, headers=auth(tok)).json()["id"]
    body = b"Deploy notes for the team.\n\napi_key = AIzaSyA1234567890abcdefghijklmnopqrstuv and call 9876543210 if stuck."
    r = client.post(f"/projects/{pid}/sources/upload", files=[("files", ("n.txt", body, "text/plain"))],
                    data={"access_label": "Team"}, headers=auth(tok))
    assert r.json()["results"][0]["source"]["redactions"] >= 2
    text = " ".join(e["text"] for e in client.get(f"/projects/{pid}/evidence", headers=auth(tok)).json()["evidence"])
    assert "AIza" not in text and "9876543210" not in text


# ---------- 4-7: claims and verification ----------

def test_quote_matcher_exact_fuzzy_and_invented():
    text = "Dropping Razorpay for now. The sponsor asked us to pause payments until the MoU is signed."
    kind, score, s, e = find_quote("the sponsor asked us to pause payments", text)
    assert kind == "exact" and text[s:e] == "The sponsor asked us to pause payments"
    kind, score, _, _ = find_quote("The sponsor asked us to pause payment until the MOU is signed", text)
    assert kind == "fuzzy" and score >= 90
    assert find_quote("payments will resume in November", text)[0] == "none"
    assert find_quote("MoU", text)[0] == "none"  # too short to prove anything


def test_demo_analysis_generates_and_verifies_claims(client, demo):
    data = claims_of(client, demo)
    assert len(data["claims"]) >= 10
    decision = by_statement(data, "PAYMENTS_ENABLED")
    d = client.get(f"/claims/{decision['id']}", headers=auth(demo["tokens"][REVIEWER])).json()
    exact_sources = {c["evidence"]["source"] for c in d["citations"] if c["match"] == "exact"}
    assert decision["gate1"] == "pass" and len(exact_sources) == 2  # corroborated by two independent sources
    assert decision["confidence"] == "conflicting"  # ...but a newer decision may replace it (timeline check)

    altered = by_statement(data, "Riya owns the registration API.")
    d = client.get(f"/claims/{altered['id']}", headers=auth(demo["tokens"][REVIEWER])).json()
    assert d["citations"][0]["match"] == "fuzzy" and altered["gate1"] == "fail"
    assert altered["confidence"] == "unverified"  # altered words are never accepted as verified

    invented = by_statement(data, "resume in November")
    assert invented["gate1"] == "fail" and invented["confidence"] == "unverified"

    missing = by_statement(data, "analytics page")
    detail = client.get(f"/claims/{missing['id']}", headers=auth(demo["tokens"][REVIEWER])).json()
    assert detail["citations"][0]["match"] == "missing_evidence" and missing["confidence"] == "unverified"

    unsupported = by_statement(data, "no automated tests")
    assert unsupported["gate1"] == "pass" and unsupported["support"] == "unrelated"
    assert unsupported["confidence"] == "unverified"

    ov = client.get(f"/projects/{demo['project_id']}", headers=auth(demo["tokens"][REVIEWER])).json()
    assert ov["latest_job"]["status"] == "done"
    assert ov["latest_job"]["stats"]["rejected_quotes"] >= 2


def test_claim_detail_has_highlight_offsets(client, demo):
    decision = by_statement(claims_of(client, demo), "PAYMENTS_ENABLED")
    d = client.get(f"/claims/{decision['id']}", headers=auth(demo["tokens"][REVIEWER])).json()
    for cit in d["citations"]:
        text = cit["evidence"]["text"]
        assert cit["match"] in ("exact", "fuzzy")
        assert text[cit["start"]:cit["end"]].lower().startswith(cit["quote"].lower()[:10])


# ---------- 8-9: conflicts and gaps ----------

def test_conflict_and_gaps_detected(client, demo):
    tok = auth(demo["tokens"][REVIEWER])
    conflicts = client.get(f"/projects/{demo['project_id']}/conflicts", headers=tok).json()["conflicts"]
    status = [k for k in conflicts if k["kind"] == "status"]
    # Four sources disagree about one topic -> exactly ONE conflict listing every source.
    assert len(status) == 1 and "excel export" in status[0]["explanation"].lower()
    assert len(status[0]["side_a"]) + len(status[0]["side_b"]) >= 3
    assert all(c["confidence"] == "conflicting" for c in status[0]["side_a"] + status[0]["side_b"])
    assert status[0]["newer_side"] == "b"  # the "not done" side has the newer evidence
    superseded = [k for k in conflicts if k["kind"] == "superseded"]
    # Two newer messages replace the same older decision -> still ONE timeline conflict.
    assert len(superseded) == 1 and len(superseded[0]["side_b"]) == 2
    assert any("switched back on" in c["statement"] for c in superseded[0]["side_b"])
    assert len([g for g in client.get(f"/projects/{demo['project_id']}/gaps", headers=tok).json()["gaps"]
                if g["kind"] == "conflict"]) == 2  # one question per conflict, not per pair
    gaps = client.get(f"/projects/{demo['project_id']}/gaps", headers=tok).json()["gaps"]
    kinds = {g["kind"] for g in gaps}
    assert {"missing_owner", "open_question", "conflict"} <= kinds
    assert any("sponsor mou follow-up" in g["question"] for g in gaps if g["kind"] == "missing_owner")


def test_leaver_answer_becomes_attested_evidence(client, demo):
    pid = demo["project_id"]
    gaps = client.get(f"/projects/{pid}/gaps", headers=auth(demo["tokens"][LEAVER])).json()["gaps"]
    gap = next(g for g in gaps if g["kind"] == "missing_owner")
    # Only the departing member may answer.
    r = client.post(f"/gaps/{gap['id']}/answer", json={"answer": "Priya should own it."},
                    headers=auth(demo["tokens"][REVIEWER]))
    assert r.status_code == 403
    r = client.post(f"/gaps/{gap['id']}/answer", json={"answer": "Priya should follow up with Arjun."},
                    headers=auth(demo["tokens"][LEAVER]))
    assert r.status_code == 200 and r.json()["status"] == "answered"
    ev = client.get(f"/evidence/{r.json()['answer_evidence_id']}", headers=auth(demo["tokens"][REVIEWER])).json()
    assert ev["kind"] == "attestation" and ev["author"] == LEAVER
    claim = client.get(f"/claims/{gap['claim_id']}", headers=auth(demo["tokens"][REVIEWER])).json()
    assert claim["leaver_note"] == "Priya should follow up with Arjun."


# ---------- 10-12: review and handover ----------

def _approve_all_resolvable(client, demo):
    tok = auth(demo["tokens"][REVIEWER])
    pid = demo["project_id"]
    reopened = None
    for conflict in client.get(f"/projects/{pid}/conflicts", headers=tok).json()["conflicts"]:
        if conflict["status"] != "open":
            continue
        sides = conflict["side_a"] + conflict["side_b"]
        if conflict["kind"] == "status":
            winner = next(c for c in sides if c["status"] == "reopened")
            reopened = winner
        else:
            winner = conflict["side_b"][0]  # the newer decision
        r = client.post(f"/conflicts/{conflict['id']}/resolve",
                        json={"winner_claim_id": winner["id"], "note": "Newer source is current."}, headers=tok)
        assert r.status_code == 200 and r.json()["status"] == "resolved"
        if conflict["kind"] == "status":
            losers = [c for c in r.json()["side_a"] + r.json()["side_b"] if c["status"] == "done"]
            assert losers and all(c["review_state"] == "superseded" for c in losers)
    for c in claims_of(client, demo)["claims"]:
        if c["review_state"] != "pending":
            continue
        action = "approve" if c["confidence"] != "unverified" else "reject"
        assert client.post(f"/claims/{c['id']}/review", json={"action": action}, headers=tok).status_code == 200
    return reopened


def test_review_rules(client, demo):
    tok = auth(demo["tokens"][REVIEWER])
    data = claims_of(client, demo)
    invented = by_statement(data, "resume in November")
    r = client.post(f"/claims/{invented['id']}/review", json={"action": "approve"}, headers=tok)
    assert r.status_code == 422  # unverified needs a reason, and then is labelled reviewer-asserted
    conflicting = next(c for c in data["claims"] if c["confidence"] == "conflicting")
    r = client.post(f"/claims/{conflicting['id']}/review", json={"action": "approve"}, headers=tok)
    assert r.status_code == 409  # resolve the conflict first
    r = client.post(f"/claims/{invented['id']}/review", json={"action": "approve", "reason": "Confirmed verbally"},
                    headers=tok)
    assert r.json()["confidence"] == "reviewer_asserted"
    r = client.post(f"/claims/{invented['id']}/review", json={"action": "reject", "reason": "Not real"}, headers=tok)
    assert r.json()["review_state"] == "rejected"
    # Non-reviewers cannot review.
    r = client.post(f"/claims/{invented['id']}/review", json={"action": "approve"},
                    headers=auth(demo["tokens"][LEAVER]))
    assert r.status_code == 403


def test_handover_generation_links_and_role_views(client, demo):
    pid = demo["project_id"]
    tok = auth(demo["tokens"][REVIEWER])
    reopened = _approve_all_resolvable(client, demo)
    r = client.post(f"/claims/{reopened['id']}/review", json={"action": "reassign", "owner": "Karan Mehta"}, headers=tok)
    assert r.json()["owner_reassigned"]

    # Incoming member sees nothing before approval.
    assert client.get(f"/projects/{pid}/handover", headers=auth(demo["tokens"][NEW])).status_code == 404
    v = client.post(f"/projects/{pid}/handover/generate", headers=tok).json()
    assert client.get(f"/projects/{pid}/handover", headers=auth(demo["tokens"][NEW])).status_code == 404
    assert client.post(f"/handover/{v['id']}/approve", headers=tok).json()["status"] == "approved"

    h = client.get(f"/projects/{pid}/handover", headers=auth(demo["tokens"][NEW])).json()
    sections = {s["key"]: s for s in h["content"]["sections"]}
    assert len(sections) == 8
    nxt = sections["next"]["items"]
    assert nxt and nxt[0]["status"] == "reopened" and nxt[0]["action"].startswith("Fix and re-test")
    own_text = " ".join(i["text"] for i in sections["own"]["items"])
    assert "500 rows" in own_text  # reassigned to Karan
    texts = " ".join(i["text"] for s in sections.values() for i in s["items"])
    assert "resume in November" not in texts and "no automated tests" not in texts  # unverified never shown
    assert "Excel export is done" not in texts  # superseded side of the conflict
    assert "switched back on" in texts and "stay disabled" not in texts  # newer decision replaced the older
    # Restricted sponsor contact is hidden from Karan (Leads) but counted.
    assert "Arjun Rao" not in texts and sections["contacts"]["hidden_count"] == 1
    # Every claim item links to evidence Karan is allowed to open.
    for s in sections.values():
        for item in s["items"]:
            if item["claim_id"]:
                assert item["evidence"], item
                for e in item["evidence"]:
                    assert client.get(f"/evidence/{e['evidence_id']}", headers=auth(demo["tokens"][NEW])).status_code == 200
    # The reviewer (Restricted) sees the contact.
    full = client.get(f"/projects/{pid}/handover", headers=tok).json()
    assert any("Arjun Rao" in i["text"] for s in full["content"]["sections"] for i in s["items"])
    # Acknowledgement.
    r = client.post(f"/handover/{v['id']}/ack", json={"section": "own"}, headers=auth(demo["tokens"][NEW]))
    assert r.json()["acknowledged"] == ["own"]
    audit = client.get(f"/projects/{pid}/audit", headers=tok).json()
    actions = {a["action"] for a in audit}
    assert {"handover.approved", "handover.acknowledged", "conflict.resolved", "claim.approve"} <= actions


# ---------- 13: access control ----------

def test_access_control(client, demo):
    pid = demo["project_id"]
    # Viewer and incoming member can't see raw claims, evidence lists or the audit log.
    for who in (NEW, VIEWER):
        assert client.get(f"/projects/{pid}/claims", headers=auth(demo["tokens"][who])).status_code == 403
        assert client.get(f"/projects/{pid}/audit", headers=auth(demo["tokens"][who])).status_code == 403
    # Leads-level departing member can't open Restricted evidence.
    rev_ev = client.get(f"/projects/{pid}/evidence", headers=auth(demo["tokens"][REVIEWER])).json()["evidence"]
    secret = next(e for e in rev_ev if "Rs 40,000" in e["text"])
    assert client.get(f"/evidence/{secret['id']}", headers=auth(demo["tokens"][LEAVER])).status_code == 403
    leaver_list = client.get(f"/projects/{pid}/evidence", headers=auth(demo["tokens"][LEAVER])).json()
    assert all("40,000" not in e["text"] for e in leaver_list["evidence"]) and leaver_list["hidden_count"] == 2
    # A different visitor can't see this project at all.
    other = signup(client)
    assert client.get(f"/projects/{pid}", headers=auth(other)).status_code == 404
    assert client.get(f"/evidence/{secret['id']}", headers=auth(other)).status_code == 404
    # Nor act as someone in another workspace.
    r = client.post("/auth/act-as", json={"user_id": demo["people"][REVIEWER]}, headers=auth(other))
    assert r.status_code == 404
    # No token at all.
    assert client.get(f"/projects/{pid}").status_code == 401


def test_ai_not_configured_is_reported(client):
    from app.llm.provider import set_providers_for_tests
    set_providers_for_tests([])
    tok = signup(client)
    pid = client.post("/projects", json={"name": "No AI"}, headers=auth(tok)).json()["id"]
    client.post(f"/projects/{pid}/sources/upload", files=[("files", ("a.md", b"We decided to use Postgres for everything.", "text/markdown"))],
                data={"access_label": "Team"}, headers=auth(tok))
    client.post(f"/projects/{pid}/analyse", headers=auth(tok))
    job = client.get(f"/projects/{pid}/jobs/latest", headers=auth(tok)).json()
    assert job["status"] == "failed" and "GEMINI_API_KEY" in job["error"]


def test_corrected_state_enters_handover(client, demo):
    tok = auth(demo["tokens"][REVIEWER])
    claim = by_statement(claims_of(client, demo), "CI fails every Monday")
    r = client.post(f"/claims/{claim['id']}/review",
                    json={"action": "edit", "statement": "CI fails every Monday when the weekly test token expires."},
                    headers=tok)
    assert r.json()["review_state"] == "corrected" and r.json()["confidence"] == "reviewer_asserted"
    assert r.json()["original_statement"] != r.json()["statement"]


def test_chat_and_json_imports(client):
    import json as _json
    tok = signup(client)
    pid = client.post("/projects", json={"name": "Imports"}, headers=auth(tok)).json()["id"]
    chat = (b"28/10/2026, 18:04 - Priya: The sponsor signed the MoU today!\n"
            b"28/10/2026, 18:06 - Priya: Karan please turn payments back on after the fest\n"
            b"and test checkout first.\n"
            b"[29/10/26, 09:12:30] Riya: CI failed again because the token expired.\n")
    issues = _json.dumps([{"number": 92, "title": "Excel export breaks above 500 rows", "state": "open",
                           "state_reason": "reopened", "body": "Times out above 500 rows.",
                           "user": {"login": "anika"}, "updated_at": "2026-10-02T10:00:00Z",
                           "comments": [{"body": "I have not started the fix yet.", "user": {"login": "riya-dev"},
                                         "created_at": "2026-10-03T09:00:00Z"}]}]).encode()
    slack = _json.dumps([{"type": "message", "user_name": "priya", "text": "Freeze the schema before the fest.",
                          "ts": "1790000000.000100"}]).encode()
    r = client.post(f"/projects/{pid}/sources/upload", data={"access_label": "Team"}, headers=auth(tok), files=[
        ("files", ("whatsapp.txt", chat, "text/plain")),
        ("files", ("issues.json", issues, "application/json")),
        ("files", ("slack.json", slack, "application/json")),
        ("files", ("broken.json", b"{not json", "application/json")),
    ])
    res = {x["filename"]: x for x in r.json()["results"]}
    assert res["whatsapp.txt"]["source"]["kind"] == "chat" and res["whatsapp.txt"]["source"]["unit_count"] == 3
    assert res["issues.json"]["source"]["unit_count"] == 2 and res["slack.json"]["source"]["unit_count"] == 1
    assert not res["broken.json"]["ok"]
    ev = client.get(f"/projects/{pid}/evidence", headers=auth(tok)).json()["evidence"]
    msg = next(e for e in ev if e["kind"] == "chat_message" and "turn payments back on" in e["text"])
    assert msg["author"] == "Priya" and msg["date"] == "2026-10-28 18:06" and "test checkout" in msg["text"]
    assert msg["source_type"] == "chat"
    issue = next(e for e in ev if e["kind"] == "github_issue")
    assert "[reopened]" in issue["text"] and issue["author"] == "anika" and issue["date"] == "2026-10-02 10:00"
    assert any(e["kind"] == "chat_message" and e["author"] == "priya" for e in ev)


# ---------- own project: a judge brings their own files and people ----------

def test_own_project_from_scratch(client):
    import zipfile

    tok = signup(client, name="Dr. Mehra")
    body = {"name": "Judge project", "your_name": "Dr. Mehra",
            "departing": {"name": "Riya Sharma", "handle": "riya-dev", "access_level": "Leads"},
            "incoming": {"name": "Karan Mehta", "handle": "karan-m", "access_level": "Leads"}}
    pid = client.post("/projects", json=body, headers=auth(tok)).json()["id"]
    ov = client.get(f"/projects/{pid}", headers=auth(tok)).json()
    assert ov["project"]["departing"] == "Riya Sharma" and ov["project"]["incoming"] == "Karan Mehta"
    assert ov["me"]["name"] == "Dr. Mehra" and ov["me"]["role"] == "admin"

    # Upload the downloadable sample pack, file by file, with the suggested labels.
    z = zipfile.ZipFile(io.BytesIO(client.get("/samples.zip").content))
    assert "LABELS.txt" in z.namelist()
    from app.demo import SEED_FILES
    from app.models import LABELS
    for filename, label in SEED_FILES:
        r = client.post(f"/projects/{pid}/sources/upload", files=[("files", (filename, z.read(filename)))],
                        data={"access_label": LABELS[label]}, headers=auth(tok))
        assert r.json()["results"][0]["ok"], r.text
    assert client.post(f"/projects/{pid}/analyse", headers=auth(tok)).status_code == 200
    ov = client.get(f"/projects/{pid}", headers=auth(tok)).json()
    assert ov["latest_job"]["status"] == "done" and ov["counts"]["claims"] >= 10

    # Resolve conflicts, approve what can be approved, and share the handover.
    for k in client.get(f"/projects/{pid}/conflicts", headers=auth(tok)).json()["conflicts"]:
        client.post(f"/conflicts/{k['id']}/resolve", json={"winner_claim_id": k["side_b"][0]["id"], "note": "newer"},
                    headers=auth(tok))
    for c in client.get(f"/projects/{pid}/claims", headers=auth(tok)).json()["claims"]:
        if c["review_state"] == "pending" and c["confidence"] in ("verified", "corroborated", "weak"):
            client.post(f"/claims/{c['id']}/review", json={"action": "approve"}, headers=auth(tok))
    v = client.post(f"/projects/{pid}/handover/generate", headers=auth(tok)).json()
    client.post(f"/handover/{v['id']}/approve", headers=auth(tok))

    people = {p["name"]: p["id"] for p in client.get("/auth/me", headers=auth(tok)).json()["people"]}
    karan = client.post("/auth/act-as", json={"user_id": people["Karan Mehta"]}, headers=auth(tok)).json()["token"]
    h = client.get(f"/projects/{pid}/handover", headers=auth(karan)).json()
    sections = {s["key"]: s for s in h["content"]["sections"]}
    assert h["content"]["departing"] == "Riya Sharma"
    assert any(i["claim_id"] for s in sections.values() for i in s["items"])
    assert sections["contacts"]["hidden_count"] >= 1  # Restricted sponsor notes stay hidden from Leads
