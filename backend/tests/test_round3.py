"""Round 3: real accounts and invites, the living handover, and Ask Baton."""

from conftest import auth, signup
from test_workflow import LEAVER, NEW, REVIEWER, _approve_all_resolvable, claims_of

UPDATE_NOTE = (
    b"# Standup 2026-11-12\n\nDate: 2026-11-12\nAuthor: Karan Mehta\n\n"
    b"The attendee Excel export fix is done and deployed. Chunked writes now work above 500 rows.\n\n"
    b"Venue Wi-Fi for check-in is provided by the college IT desk.\n"
)


def _project_with_people(client, reviewer_tok):
    body = {
        "name": "Library app",
        "departing": {"name": "Riya Sharma", "handle": "riya-dev", "access_level": "Leads"},
        "incoming": {"name": "Karan Mehta", "handle": "karan-m", "access_level": "Leads"},
    }
    r = client.post("/projects", json=body, headers=auth(reviewer_tok))
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    members = {m["name"]: m for m in client.get(f"/projects/{pid}/members", headers=auth(reviewer_tok)).json()["members"]}
    return pid, members


# ---------- accounts ----------


def test_signup_signin_and_bad_input(client):
    r = client.post("/auth/signup", json={"name": "Asha", "email": "asha@example.com", "password": "short"})
    assert r.status_code == 422  # password too short
    r = client.post("/auth/signup", json={"name": "Asha", "email": "not-an-email", "password": "long-enough-1"})
    assert r.status_code == 422
    tok = signup(client, "Asha", "Asha@Example.com")
    assert client.get("/auth/me", headers=auth(tok)).json()["registered"] is True
    r = client.post("/auth/signup", json={"name": "Asha 2", "email": "asha@example.com", "password": "long-enough-1"})
    assert r.status_code == 409  # same email (case-insensitive)
    assert client.post("/auth/signin", json={"email": "asha@example.com", "password": "wrong-password"}).status_code == 401
    r = client.post("/auth/signin", json={"email": " ASHA@example.com ", "password": "correct-horse-9"})
    assert r.status_code == 200 and r.json()["user"]["name"] == "Asha"
    # Garbage tokens are refused cleanly.
    assert client.get("/auth/me", headers=auth("not-a-token")).status_code == 401
    assert client.get("/projects", headers={"Authorization": ""}).status_code == 401
    # The old anonymous "guest" workspace is gone; a demo copy can't start its own project.
    assert client.post("/auth/guest").status_code in (404, 405)
    demo_tok = client.post("/auth/demo", json={"stage": "fresh"}).json()["token"]
    assert client.post("/projects", json={"name": "X project"}, headers=auth(demo_tok)).status_code == 401
    # Demo addresses can't be registered by anyone.
    r = client.post("/auth/signup", json={"name": "X", "email": "karan@baton.demo", "password": "long-enough-1"})
    assert r.status_code == 409


# ---------- invites ----------


def test_invite_accept_preview_and_remove(client):
    rev = signup(client, "Dr. Mehra")
    pid, members = _project_with_people(client, rev)
    karan_slot, riya_slot = members["Karan Mehta"], members["Riya Sharma"]
    assert karan_slot["status"] == "not_invited" and not karan_slot["joined"]

    # Before anyone joins, the reviewer can preview as them, and the audit log says so.
    people = client.get("/auth/me", headers=auth(rev)).json()["people"]
    assert {p["name"] for p in people} == {"Dr. Mehra", "Riya Sharma", "Karan Mehta"}
    as_riya = client.post("/auth/act-as", json={"user_id": riya_slot["user_id"]}, headers=auth(rev)).json()["token"]
    me = client.get("/auth/me", headers=auth(as_riya)).json()
    assert me["previewing"] and me["user"]["name"] == "Riya Sharma" and me["real_user"]["name"] == "Dr. Mehra"
    assert client.post("/projects", json={"name": "Nope"}, headers=auth(as_riya)).status_code == 401
    gaps_ok = client.get(f"/projects/{pid}/members", headers=auth(as_riya)).status_code == 200
    assert gaps_ok

    # Only reviewers/admins make invite links; a departing member can't.
    assert (
        client.post(f"/projects/{pid}/invites", json={"user_id": karan_slot["user_id"]}, headers=auth(as_riya)).status_code == 403
    )
    inv = client.post(
        f"/projects/{pid}/invites", json={"user_id": karan_slot["user_id"], "email": "karan@example.com"}, headers=auth(rev)
    ).json()
    token = inv["token"]
    assert inv["state"] == "pending" and inv["path"] == f"/invite/{token}"
    info = client.get(f"/invites/{token}").json()  # public preview, no sign-in
    assert info["project"] == "Library app" and info["name"] == "Karan Mehta" and info["role"] == "incoming"
    assert client.get("/invites/not-a-real-token").status_code == 404

    # A new link replaces the old one.
    inv2 = client.post(f"/projects/{pid}/invites", json={"user_id": karan_slot["user_id"]}, headers=auth(rev)).json()
    assert client.get(f"/invites/{token}").json()["state"] == "revoked"
    token = inv2["token"]

    # Karan signs up with his own account and accepts.
    karan = signup(client, "Karan Mehta", "karan@example.com")
    assert client.get(f"/projects/{pid}", headers=auth(karan)).status_code == 404  # not a member yet
    r = client.post(f"/invites/{token}/accept", headers=auth(karan))
    assert r.status_code == 200 and r.json()["role"] == "incoming"
    assert client.post(f"/invites/{token}/accept", headers=auth(karan)).status_code == 409  # one-time
    ov = client.get(f"/projects/{pid}", headers=auth(karan)).json()
    assert ov["me"]["role"] == "incoming" and ov["project"]["incoming"] == "Karan Mehta"
    assert any(p["id"] == pid for p in client.get("/projects", headers=auth(karan)).json())
    status = {m["name"]: m["status"] for m in client.get(f"/projects/{pid}/members", headers=auth(rev)).json()["members"]}
    assert status["Karan Mehta"] == "joined"

    # Nobody can preview as Karan any more.
    people = {p["name"] for p in client.get("/auth/me", headers=auth(rev)).json()["people"]}
    assert "Karan Mehta" not in people
    assert client.post("/auth/act-as", json={"user_id": karan_slot["user_id"]}, headers=auth(rev)).status_code == 404

    # A revoked invite can't be used.
    riya_inv = client.post(f"/projects/{pid}/invites", json={"user_id": riya_slot["user_id"]}, headers=auth(rev)).json()
    assert client.post(f"/invites/{riya_inv['id']}/revoke", headers=auth(rev)).json()["state"] == "revoked"
    riya = signup(client, "Riya Sharma")
    assert client.post(f"/invites/{riya_inv['token']}/accept", headers=auth(riya)).status_code == 409

    # Removing access is immediate.
    assert client.post(f"/projects/{pid}/members/{ov['me']['user_id']}/remove", headers=auth(karan)).status_code == 403
    assert client.post(f"/projects/{pid}/members/{ov['me']['user_id']}/remove", headers=auth(rev)).status_code == 200
    assert client.get(f"/projects/{pid}", headers=auth(karan)).status_code == 404
    me_id = client.get(f"/projects/{pid}", headers=auth(rev)).json()["me"]["user_id"]
    assert client.post(f"/projects/{pid}/members/{me_id}/remove", headers=auth(rev)).status_code == 409

    actions = [(a["action"], a["actor"]) for a in client.get(f"/projects/{pid}/audit", headers=auth(rev)).json()]
    assert ("invite.accepted", "Karan Mehta") in actions
    assert any(a == "member.removed" for a, _ in actions)


def test_demo_still_switches_people(client, demo):
    """The worked example keeps one-click switching between its people (no accounts needed)."""
    people = client.get("/auth/me", headers=auth(demo["tokens"][REVIEWER])).json()["people"]
    assert len(people) == 4
    r = client.post(
        f"/projects/{demo['project_id']}/invites", json={"user_id": demo["people"][NEW]}, headers=auth(demo["tokens"][REVIEWER])
    )
    assert r.status_code == 409


# ---------- living handover ----------


def _approve_v1(client, demo):
    pid, tok = demo["project_id"], auth(demo["tokens"][REVIEWER])
    _approve_all_resolvable(client, demo)
    v1 = client.post(f"/projects/{pid}/handover/generate", headers=tok).json()
    client.post(f"/handover/{v1['id']}/approve", headers=tok)
    for sec in ("own", "next", "unfinished", "decisions", "risks", "dependencies", "questions", "contacts"):
        client.post(f"/handover/{v1['id']}/ack", json={"section": sec}, headers=auth(demo["tokens"][NEW]))
    return v1


def test_living_handover_update_flags_changes_and_versions(client, demo):
    pid, tok = demo["project_id"], auth(demo["tokens"][REVIEWER])
    _approve_v1(client, demo)
    before = claims_of(client, demo)["claims"]
    approved_before = {c["id"] for c in before if c["review_state"] in ("approved", "corrected")}
    assert approved_before

    # Nothing new yet: an update run is refused with a clear message.
    r = client.post(f"/projects/{pid}/analyse", json={"mode": "update"}, headers=tok)
    assert r.status_code == 409 and "No new evidence" in r.json()["detail"]

    # New evidence arrives after approval.
    r = client.post(
        f"/projects/{pid}/sources/upload",
        files=[("files", ("standup-2026-11-12.md", UPDATE_NOTE))],
        data={"access_label": "Team"},
        headers=tok,
    )
    assert r.json()["results"][0]["ok"]
    assert client.get(f"/projects/{pid}", headers=tok).json()["counts"]["new_evidence"] == 2
    job = client.post(f"/projects/{pid}/analyse", json={}, headers=tok).json()  # defaults to update
    assert job["kind"] == "update"
    ov = client.get(f"/projects/{pid}", headers=tok).json()
    stats = ov["latest_job"]["stats"]
    assert ov["latest_job"]["status"] == "done", ov["latest_job"]
    assert stats["mode"] == "update" and stats["evidence_units"] == 2 and stats["claims"] == 2
    assert stats["changed_since_approval"] >= 1 and ov["counts"]["new_evidence"] == 0

    # Review decisions survived: every previously approved claim is still approved.
    after = {c["id"]: c for c in claims_of(client, demo)["claims"]}
    assert all(after[i]["review_state"] in ("approved", "corrected") for i in approved_before)

    # The approved handover now flags the affected line for everyone, including Karan.
    h = client.get(f"/projects/{pid}/handover", headers=auth(demo["tokens"][NEW])).json()
    flagged = [i for s in h["content"]["sections"] for i in s["items"] if i.get("changed_since_approval")]
    assert flagged and h["version"] == 1 and h["update_in_review"]
    assert any("500 rows" in i["text"] for i in flagged)
    # The newer quote is shown beside the old one, word-for-word and highlighted.
    newer = next(i for i in flagged if i.get("newer_evidence"))["newer_evidence"][0]
    assert (
        "done and deployed" in newer["quote"] and newer["text"][newer["start"] : newer["end"]].lower() == newer["quote"].lower()
    )

    # Reviewer settles the new conflict in favour of the newer evidence, approves the new claim, issues v2.
    new_conflicts = [
        k for k in client.get(f"/projects/{pid}/conflicts", headers=tok).json()["conflicts"] if k["status"] == "open"
    ]
    assert new_conflicts
    for k in new_conflicts:
        newest = next(c for c in k["side_a"] + k["side_b"] if "deployed" in c["statement"])
        assert (
            client.post(
                f"/conflicts/{k['id']}/resolve", json={"winner_claim_id": newest["id"], "note": "Fixed."}, headers=tok
            ).status_code
            == 200
        )
    for c in claims_of(client, demo)["claims"]:
        if c["review_state"] == "pending" and c["confidence"] != "unverified":
            client.post(f"/claims/{c['id']}/review", json={"action": "approve"}, headers=tok)
    v2 = client.post(f"/projects/{pid}/handover/generate", headers=tok).json()
    assert v2["version"] == 2 and v2["base_version"] == 1 and v2["changes"] >= 2
    draft = client.get(f"/projects/{pid}/handover", headers=tok).json()
    diff = draft["diff"]["sections"]
    assert diff and any(part["removed"] for part in diff.values()) and any(part["added"] for part in diff.values())
    assert any(i.get("change") == "added" for s in draft["content"]["sections"] for i in s["items"])
    client.post(f"/handover/{v2['id']}/approve", headers=tok)

    # Karan sees v2 with its diff; only changed sections need acknowledging again.
    h2 = client.get(f"/projects/{pid}/handover", headers=auth(demo["tokens"][NEW])).json()
    assert h2["version"] == 2 and h2["diff"]["total"] >= 1
    changed_sections = set(h2["diff"]["sections"])
    assert changed_sections and set(h2["acknowledged"]) == {s["key"] for s in h2["content"]["sections"]} - changed_sections
    assert not any(i.get("changed_since_approval") for s in h2["content"]["sections"] for i in s["items"])
    acts = {a["action"] for a in client.get(f"/projects/{pid}/audit", headers=tok).json()}
    assert {"analysis.updated", "handover.approved"} <= acts


def test_github_resync_adds_only_new_items(client, monkeypatch):
    from app.ingest import github
    from app.ingest.parsers import ParsedSource, Unit

    calls = {"n": 0}

    def fake_fetch(url, token=None):
        calls["n"] += 1
        out = ParsedSource()
        out.units = [
            Unit(
                kind="github_issue",
                text="Issue #1 [open]: Add login page",
                author="riya-dev",
                occurred_at="2026-11-01",
                location={"number": 1},
            )
        ]
        if calls["n"] > 1:
            out.units.append(
                Unit(
                    kind="github_issue",
                    text="Issue #2 [open]: Parking map is wrong",
                    author="karan-m",
                    occurred_at="2026-11-13",
                    location={"number": 2},
                )
            )
        return "club/eventapp", out

    monkeypatch.setattr(github, "fetch_repo", fake_fetch)
    import app.sources.router as sr

    monkeypatch.setattr(sr, "fetch_repo", fake_fetch)
    rev = signup(client)
    pid, _ = _project_with_people(client, rev)
    src = client.post(
        f"/projects/{pid}/sources/github", json={"repo_url": "https://github.com/club/eventapp"}, headers=auth(rev)
    ).json()
    assert src["unit_count"] == 1
    client.post(f"/projects/{pid}/analyse", json={}, headers=auth(rev))
    r = client.post(f"/projects/{pid}/check-for-changes", json={}, headers=auth(rev)).json()
    assert r["synced"][0]["new_items"] == 1 and r["new_evidence"] == 1 and r["job"]["kind"] == "update"
    r = client.post(f"/projects/{pid}/check-for-changes", json={}, headers=auth(rev)).json()
    assert r["synced"][0]["new_items"] == 0 and r["job"] is None  # nothing new: no job


# ---------- Ask Baton ----------


def test_ask_baton_cites_checked_quotes_and_respects_access(client, demo):
    pid = demo["project_id"]
    _approve_all_resolvable(client, demo)
    karan = auth(demo["tokens"][NEW])
    r = client.post(f"/projects/{pid}/ask", json={"question": "Why are online payments switched off?"}, headers=karan)
    q = r.json()
    assert r.status_code == 200 and q["status"] == "answered" and q["citations"]
    c = q["citations"][0]
    assert c["match"] == "exact" and c["text"][c["start"] : c["end"]].lower() == c["quote"].lower()

    # An invented quote is rejected, so Baton says it can't answer instead of showing it.
    q = client.post(f"/projects/{pid}/ask", json={"question": "Can you invent the deploy runbook steps?"}, headers=karan).json()
    assert q["status"] == "unanswered" and q["rejected_quotes"] == 1 and not q["citations"]

    # Restricted evidence never reaches Karan (Leads), even through Ask Baton.
    q = client.post(f"/projects/{pid}/ask", json={"question": "Who is the sponsor contact for the MoU?"}, headers=karan).json()
    assert q["status"] == "unanswered" and "Arjun" not in (q["answer"] or "")
    q = client.post(
        f"/projects/{pid}/ask",
        json={"question": "Who is the sponsor contact for the MoU?"},
        headers=auth(demo["tokens"][REVIEWER]),
    ).json()
    assert q["status"] == "answered" and "Arjun Rao" in q["citations"][0]["quote"]

    # Bad input.
    assert client.post(f"/projects/{pid}/ask", json={"question": "?"}, headers=karan).status_code == 422
    assert client.post(f"/projects/{pid}/ask", json={"question": "the and of"}, headers=karan).status_code == 422


def test_ask_unanswered_goes_to_leaver_and_comes_back_as_evidence(client, demo):
    pid = demo["project_id"]
    karan, riya = auth(demo["tokens"][NEW]), auth(demo["tokens"][LEAVER])
    q = client.post(f"/projects/{pid}/ask", json={"question": "Where is visitor parking for the fest?"}, headers=karan).json()
    assert q["status"] == "unanswered"
    sent = client.post(f"/questions/{q['id']}/send", headers=karan).json()
    assert sent["sent"] and sent["status"] == "sent"
    assert client.post(f"/questions/{q['id']}/send", headers=karan).json()["sent"]  # twice is harmless
    # Karan sees only his own questions.
    assert [x["id"] for x in client.get(f"/projects/{pid}/questions", headers=karan).json()["questions"]] == [q["id"]]

    gap = next(g for g in client.get(f"/projects/{pid}/gaps", headers=riya).json()["gaps"] if g["kind"] == "asked")
    r = client.post(f"/gaps/{gap['id']}/answer", json={"answer": "Visitor parking is behind the library."}, headers=riya)
    assert r.status_code == 200
    assert client.post(f"/gaps/{gap['id']}/answer", json={"answer": "again"}, headers=riya).status_code == 409
    mine = client.get(f"/projects/{pid}/questions", headers=karan).json()["questions"][0]
    assert mine["status"] == "answered_by_person" and mine["person_answer_by"] == LEAVER

    # The next person who asks gets the leaver's answer, cited as evidence.
    q2 = client.post(f"/projects/{pid}/ask", json={"question": "Is there parking for visitors?"}, headers=karan).json()
    assert q2["status"] == "answered" and q2["citations"][0]["kind"] == "attestation"


# ---------- reliability: the same action twice, bad input ----------


def test_repeated_actions_are_safe(client, demo):
    pid, tok = demo["project_id"], auth(demo["tokens"][REVIEWER])
    k = client.get(f"/projects/{pid}/conflicts", headers=tok).json()["conflicts"][0]
    winner = k["side_b"][0]["id"]
    assert client.post(f"/conflicts/{k['id']}/resolve", json={"winner_claim_id": winner}, headers=tok).status_code == 200
    assert client.post(f"/conflicts/{k['id']}/resolve", json={"winner_claim_id": winner}, headers=tok).status_code == 409
    assert client.post(f"/projects/{pid}/analyse", json={"mode": "sideways"}, headers=tok).status_code == 422
    gap = next(g for g in client.get(f"/projects/{pid}/gaps", headers=tok).json()["gaps"] if g["status"] == "open")
    assert client.post(f"/gaps/{gap['id']}/dismiss", json={"reason": "Not needed"}, headers=tok).status_code == 200
    assert client.post(f"/gaps/{gap['id']}/dismiss", json={"reason": "Not needed"}, headers=tok).status_code == 409
    _approve_all_resolvable(client, demo)
    v = client.post(f"/projects/{pid}/handover/generate", headers=tok).json()
    assert client.post(f"/handover/{v['id']}/approve", headers=tok).status_code == 200
    assert client.post(f"/handover/{v['id']}/approve", headers=tok).status_code == 409
    karan = auth(demo["tokens"][NEW])
    for _ in range(2):
        assert client.post(f"/handover/{v['id']}/ack", json={"section": "own"}, headers=karan).json()["acknowledged"] == ["own"]
    assert client.post(f"/handover/{v['id']}/ack", json={"section": "nope"}, headers=karan).status_code == 422
    # Unknown ids give clean 404s, not crashes.
    for path in ("/conflicts/x/resolve", "/gaps/x/answer", "/handover/x/approve", "/questions/x/send", "/invites/x/revoke"):
        body = {"answer": "hello there"} if "gaps" in path else {}
        assert client.post(path, json=body, headers=tok).status_code == 404, path
    assert client.get("/projects/does-not-exist", headers=tok).status_code == 404


# ---------- demo sign-ins: every judge gets a private copy ----------


def test_demo_signins_open_private_copies(client):
    info = client.get("/auth/demo/info").json()
    assert len(info["accounts"]) == 3 and info["password"] and info["private"] is True
    pw = info["password"]
    # Judge A signs in as the reviewer: a private copy, already analysed, reviewed and handed over (v1).
    a = client.post("/auth/signin", json={"email": "reviewer@baton.demo", "password": pw}).json()
    assert a["sandbox"] == "new"
    pid_a = a["project_id"]
    ov = client.get(f"/projects/{pid_a}", headers=auth(a["token"])).json()
    assert ov["handover"]["approved_version"] == 1 and ov["counts"]["new_evidence"] == 0
    # In the same browser, signing in as Karan switches person inside the SAME copy.
    k = client.post("/auth/signin", json={"email": "karan@baton.demo", "password": pw}, headers=auth(a["token"])).json()
    assert k["sandbox"] == "existing"
    h = client.get(f"/projects/{pid_a}/handover", headers=auth(k["token"])).json()
    assert h["status"] == "approved" and any(sec["items"] for sec in h["content"]["sections"])
    # Judge B (another browser) gets a different copy and can't see or touch judge A's.
    b = client.post("/auth/signin", json={"email": "reviewer@baton.demo", "password": pw}).json()
    assert b["project_id"] != pid_a
    assert client.get(f"/projects/{pid_a}", headers=auth(b["token"])).status_code == 404
    r = client.post(
        f"/projects/{b['project_id']}/sources/upload",
        headers=auth(b["token"]),
        data={"access_label": "Team"},
        files=[("files", ("standup.md", UPDATE_NOTE))],
    )
    assert r.status_code == 200
    assert client.get(f"/projects/{pid_a}", headers=auth(a["token"])).json()["counts"]["new_evidence"] == 0
    # Restart gives a fresh copy and deletes the old one.
    r = client.post("/auth/demo/restart", headers=auth(b["token"])).json()
    assert r["project_id"] != b["project_id"]
    assert client.get(f"/projects/{r['project_id']}", headers=auth(r["token"])).status_code == 200
    assert client.get(f"/projects/{b['project_id']}", headers=auth(r["token"])).status_code == 404
    # Wrong demo password is refused; demo copies can't be restarted by real accounts.
    assert client.post("/auth/signin", json={"email": "karan@baton.demo", "password": "nope"}).status_code == 401
    assert client.post("/auth/demo/restart", headers=auth(signup(client))).status_code == 409


def test_old_demo_copies_are_cleaned_up(client):
    from datetime import datetime, timedelta, timezone

    from app.db import SessionLocal
    from app.models import Account, Project
    from app.sandbox import cleanup_old_sandboxes

    d = client.post("/auth/demo", json={"stage": "fresh"}).json()
    with SessionLocal() as db:
        acc_id = db.get(Project, d["project_id"]).account_id
        db.get(Account, acc_id).created_at = datetime.now(timezone.utc) - timedelta(hours=30)
        db.commit()
    assert cleanup_old_sandboxes() >= 1
    with SessionLocal() as db:
        assert db.get(Project, d["project_id"]) is None and db.get(Account, acc_id) is None


# ---------- scanned PDFs and images (OCR) ----------


def _png() -> bytes:
    import pymupdf

    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 20), 0)
    pix.clear_with(255)
    return pix.tobytes("png")


def _scanned_pdf() -> bytes:
    import pymupdf

    doc = pymupdf.open()
    for _ in range(2):
        page = doc.new_page()
        page.insert_image(page.rect, stream=_png())  # an image only: no text layer, like a scan
    return doc.tobytes()


def test_scans_and_images_are_transcribed(client):
    rev = signup(client)
    pid, _ = _project_with_people(client, rev)
    r = client.post(
        f"/projects/{pid}/sources/upload",
        headers=auth(rev),
        data={"access_label": "Team"},
        files=[("files", ("whiteboard.png", _png())), ("files", ("scanned-minutes.pdf", _scanned_pdf()))],
    )
    res = {x["filename"]: x for x in r.json()["results"]}
    assert res["whiteboard.png"]["ok"] and res["scanned-minutes.pdf"]["ok"], r.text
    assert res["scanned-minutes.pdf"]["source"]["coverage"]["ocr_pages"] == 2
    units = client.get(f"/projects/{pid}/evidence", headers=auth(rev)).json()
    units = units["evidence"] if isinstance(units, dict) else units
    ocr = [u for u in units if (u.get("location") or {}).get("transcribed")]
    assert len(ocr) >= 3 and all("projector" in u["text"] or "whiteboard" in u["text"] for u in ocr)


def test_scan_when_ai_is_down_is_reported_not_crashed(client):
    from app.llm.provider import set_providers_for_tests

    rev = signup(client)
    pid, _ = _project_with_people(client, rev)
    set_providers_for_tests([])
    r = client.post(
        f"/projects/{pid}/sources/upload",
        headers=auth(rev),
        data={"access_label": "Team"},
        files=[("files", ("photo.jpg", _png()))],
    ).json()["results"][0]
    assert not r["ok"] and r["source"]["status"] == "unreadable" and "transcribed" in r["source"]["error"]


def test_handover_pdf_is_a_real_file_and_respects_access(client, demo):
    import pymupdf

    pid = demo["project_id"]
    _approve_all_resolvable(client, demo)
    tok = auth(demo["tokens"][REVIEWER])
    v = client.post(f"/projects/{pid}/handover/generate", headers=tok).json()
    client.post(f"/handover/{v['id']}/approve", headers=tok)
    r = client.get(f"/projects/{pid}/handover/pdf", headers=auth(demo["tokens"][NEW]))
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert "attachment" in r.headers["content-disposition"]
    text = "".join(p.get_text() for p in pymupdf.open(stream=r.content, filetype="pdf"))
    assert "What you own" in text and "Version 1" in text
    assert "Arjun Rao" not in text  # Restricted contact never reaches a Leads reader, even in the PDF
    full = "".join(
        p.get_text()
        for p in pymupdf.open(stream=client.get(f"/projects/{pid}/handover/pdf", headers=tok).content, filetype="pdf")
    )
    assert "Arjun Rao" in full
    assert client.get(f"/projects/{pid}/handover/pdf").status_code == 401


def test_busy_ai_is_retried_and_leftovers_finish_later(client, demo, monkeypatch):
    """A batch that hits a busy AI is retried; if it still fails, its evidence waits for the next update run."""
    import app.extract.service as ex
    from app.llm.provider import AIUnavailable

    pid, tok = demo["project_id"], auth(demo["tokens"][REVIEWER])
    real = ex.ask_extract
    calls = {"n": 0}

    def flaky(db, batch, filenames):
        calls["n"] += 1
        if calls["n"] == 1:
            raise AIUnavailable("503 UNAVAILABLE: high demand")  # first try busy, retry works
        return real(db, batch, filenames)

    monkeypatch.setattr(ex, "ask_extract", flaky)
    r = client.post(
        f"/projects/{pid}/sources/upload",
        headers=tok,
        data={"access_label": "Team"},
        files=[("files", ("standup.md", UPDATE_NOTE))],
    )
    assert r.status_code == 200
    client.post(f"/projects/{pid}/analyse", json={}, headers=tok)
    job = client.get(f"/projects/{pid}", headers=tok).json()["latest_job"]
    assert job["status"] == "done" and job["stats"]["claims"] == 2 and calls["n"] == 2

    def down(db, batch, filenames):
        raise AIUnavailable("429 RESOURCE_EXHAUSTED")

    monkeypatch.setattr(ex, "ask_extract", down)
    client.post(
        f"/projects/{pid}/sources/upload",
        headers=tok,
        data={"access_label": "Team"},
        files=[("files", ("standup-2.md", UPDATE_NOTE.replace(b"Standup", b"Second standup")))],
    )
    client.post(f"/projects/{pid}/analyse", json={}, headers=tok)
    ov = client.get(f"/projects/{pid}", headers=tok).json()
    assert ov["latest_job"]["status"] == "failed" and "Nothing was lost" in ov["latest_job"]["error"]
    assert ov["counts"]["new_evidence"] == 2  # still waiting, nothing half-saved


def test_second_opinion_for_an_over_strict_support_check(client, demo):
    tok = auth(demo["tokens"][REVIEWER])
    claims = claims_of(client, demo)["claims"]
    strict = next(c for c in claims if c["statement"] == "The registration API has no automated tests.")
    # This one's quote is real but doesn't support the claim: the first check said "unrelated".
    detail = client.get(f"/claims/{strict['id']}", headers=tok).json()
    assert detail["support"] == "unrelated" and detail["confidence"] == "unverified"
    r = client.post(f"/claims/{strict['id']}/second-opinion", headers=tok)
    assert r.status_code == 200 and r.json()["support"] == "supports" and "Second opinion" in r.json()["support_reason"]
    assert client.post(f"/claims/{strict['id']}/second-opinion", headers=tok).status_code == 409  # already agrees
    invented = next(c for c in claims if c["statement"] == "Payments will resume in November.")
    assert client.post(f"/claims/{invented['id']}/second-opinion", headers=tok).status_code == 409  # no real quote
    assert client.post(f"/claims/{strict['id']}/second-opinion", headers=auth(demo["tokens"][NEW])).status_code in (403, 404)
