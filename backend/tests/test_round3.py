"""Round 3: real accounts and invites, the living handover, and Ask Baton."""
from conftest import auth, signup
from test_workflow import LEAVER, NEW, REVIEWER, _approve_all_resolvable, claims_of

UPDATE_NOTE = (b"# Standup 2026-11-12\n\nDate: 2026-11-12\nAuthor: Karan Mehta\n\n"
               b"The attendee Excel export fix is done and deployed. Chunked writes now work above 500 rows.\n\n"
               b"Venue Wi-Fi for check-in is provided by the college IT desk.\n")


def _project_with_people(client, reviewer_tok):
    body = {"name": "Library app",
            "departing": {"name": "Riya Sharma", "handle": "riya-dev", "access_level": "Leads"},
            "incoming": {"name": "Karan Mehta", "handle": "karan-m", "access_level": "Leads"}}
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
    # Guests (no account) can't start their own project.
    guest = client.post("/auth/guest").json()["token"]
    assert client.post("/projects", json={"name": "X project"}, headers=auth(guest)).status_code == 401


def test_guest_upgrades_in_place(client):
    guest = client.post("/auth/guest").json()["token"]
    acc = client.get("/auth/me", headers=auth(guest)).json()["account"]["id"]
    r = client.post("/auth/signup", json={"name": "Meera", "email": "meera@example.com", "password": "long-enough-1"},
                    headers=auth(guest))
    me = client.get("/auth/me", headers=auth(r.json()["token"])).json()
    assert me["account"]["id"] == acc and me["registered"]


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
    assert client.post(f"/projects/{pid}/invites", json={"user_id": karan_slot["user_id"]},
                       headers=auth(as_riya)).status_code == 403
    inv = client.post(f"/projects/{pid}/invites", json={"user_id": karan_slot["user_id"], "email": "karan@example.com"},
                      headers=auth(rev)).json()
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
    r = client.post(f"/projects/{demo['project_id']}/invites", json={"user_id": demo["people"][NEW]},
                    headers=auth(demo["tokens"][REVIEWER]))
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
    v1 = _approve_v1(client, demo)
    before = claims_of(client, demo)["claims"]
    approved_before = {c["id"] for c in before if c["review_state"] in ("approved", "corrected")}
    assert approved_before

    # Nothing new yet: an update run is refused with a clear message.
    r = client.post(f"/projects/{pid}/analyse", json={"mode": "update"}, headers=tok)
    assert r.status_code == 409 and "No new evidence" in r.json()["detail"]

    # New evidence arrives after approval.
    r = client.post(f"/projects/{pid}/sources/upload", files=[("files", ("standup-2026-11-12.md", UPDATE_NOTE))],
                    data={"access_label": "Team"}, headers=tok)
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

    # Reviewer settles the new conflict in favour of the newer evidence, approves the new claim, issues v2.
    new_conflicts = [k for k in client.get(f"/projects/{pid}/conflicts", headers=tok).json()["conflicts"]
                     if k["status"] == "open"]
    assert new_conflicts
    for k in new_conflicts:
        newest = next(c for c in k["side_a"] + k["side_b"] if "deployed" in c["statement"])
        assert client.post(f"/conflicts/{k['id']}/resolve", json={"winner_claim_id": newest["id"], "note": "Fixed."},
                           headers=tok).status_code == 200
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
    assert changed_sections and set(h2["acknowledged"]) == {
        s["key"] for s in h2["content"]["sections"]} - changed_sections
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
        out.units = [Unit(kind="github_issue", text="Issue #1 [open]: Add login page", author="riya-dev",
                          occurred_at="2026-11-01", location={"number": 1})]
        if calls["n"] > 1:
            out.units.append(Unit(kind="github_issue", text="Issue #2 [open]: Parking map is wrong",
                                  author="karan-m", occurred_at="2026-11-13", location={"number": 2}))
        return "club/eventapp", out

    monkeypatch.setattr(github, "fetch_repo", fake_fetch)
    import app.sources.router as sr
    monkeypatch.setattr(sr, "fetch_repo", fake_fetch)
    rev = signup(client)
    pid, _ = _project_with_people(client, rev)
    src = client.post(f"/projects/{pid}/sources/github", json={"repo_url": "https://github.com/club/eventapp"},
                      headers=auth(rev)).json()
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
    assert c["match"] == "exact" and c["text"][c["start"]:c["end"]].lower() == c["quote"].lower()

    # An invented quote is rejected, so Baton says it can't answer instead of showing it.
    q = client.post(f"/projects/{pid}/ask", json={"question": "Can you invent the deploy runbook steps?"}, headers=karan).json()
    assert q["status"] == "unanswered" and q["rejected_quotes"] == 1 and not q["citations"]

    # Restricted evidence never reaches Karan (Leads), even through Ask Baton.
    q = client.post(f"/projects/{pid}/ask", json={"question": "Who is the sponsor contact for the MoU?"},
                    headers=karan).json()
    assert q["status"] == "unanswered" and "Arjun" not in (q["answer"] or "")
    q = client.post(f"/projects/{pid}/ask", json={"question": "Who is the sponsor contact for the MoU?"},
                    headers=auth(demo["tokens"][REVIEWER])).json()
    assert q["status"] == "answered" and "Arjun Rao" in q["citations"][0]["quote"]

    # Bad input.
    assert client.post(f"/projects/{pid}/ask", json={"question": "?"}, headers=karan).status_code == 422
    assert client.post(f"/projects/{pid}/ask", json={"question": "the and of"}, headers=karan).status_code == 422


def test_ask_unanswered_goes_to_leaver_and_comes_back_as_evidence(client, demo):
    pid = demo["project_id"]
    karan, riya = auth(demo["tokens"][NEW]), auth(demo["tokens"][LEAVER])
    q = client.post(f"/projects/{pid}/ask", json={"question": "Where is visitor parking for the fest?"},
                    headers=karan).json()
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
