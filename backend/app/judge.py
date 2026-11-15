"""Ready-made demo accounts for judges.

Three real accounts (reviewer, person leaving, person taking over) share one synthetic EventApp project that
is already analysed, reviewed and handed over (version 1), with both people joined through invites. A judge can
sign in with the published credentials and immediately try what happens next: Ask Baton as the new member,
answer questions as the leaver, upload newer evidence as the reviewer and issue version 2, or invite someone.
Anyone signed in to one of these accounts can reset the project to that starting state.

The project is built by calling Baton's own API in-process, so it goes through exactly the same code paths as
a person clicking through the app. The AI answers come from the saved responses for the worked example
(seed/eventapp/llm_cache.json), so building it needs no live AI call when the cache matches.
"""
import logging
import os
import threading

from .db import SessionLocal

log = logging.getLogger("baton.judge")
PASSWORD = os.environ.get("JUDGE_DEMO_PASSWORD") or "Baton-Judge-2026"
REVIEWER = ("Priya Nair", "reviewer@baton.demo")
LEAVER = ("Riya Sharma", "riya@baton.demo")
NEWCOMER = ("Karan Mehta", "karan@baton.demo")
PROJECT_NAME = "EventApp (shared demo for judges)"
_lock = threading.Lock()
state = {"status": "idle", "error": None}


def accounts() -> list[dict]:
    return [{"role": "reviewer", "name": REVIEWER[0], "email": REVIEWER[1]},
            {"role": "departing", "name": LEAVER[0], "email": LEAVER[1]},
            {"role": "incoming", "name": NEWCOMER[0], "email": NEWCOMER[1]}]


def _client():
    from fastapi.testclient import TestClient

    from .main import app

    return TestClient(app)  # no context manager: the running app's startup isn't repeated


def _token(c, name: str, email: str) -> str:
    r = c.post("/auth/signin", json={"email": email, "password": PASSWORD})
    if r.status_code == 200:
        return r.json()["token"]
    r = c.post("/auth/signup", json={"name": name, "email": email, "password": PASSWORD})
    r.raise_for_status()
    return r.json()["token"]


def _wipe(project_id: str) -> None:
    from .models import (Acknowledgement, AuditEvent, Claim, ClaimEvidence, Conflict, EvidenceUnit, Gap,
                         HandoverVersion, Invite, Job, Membership, Project, Question, Review, Source)

    with SessionLocal() as db:
        claim_ids = [c for (c,) in db.query(Claim.id).filter_by(project_id=project_id)]
        version_ids = [v for (v,) in db.query(HandoverVersion.id).filter_by(project_id=project_id)]
        if claim_ids:
            db.query(ClaimEvidence).filter(ClaimEvidence.claim_id.in_(claim_ids)).delete(synchronize_session=False)
            db.query(Review).filter(Review.claim_id.in_(claim_ids)).delete(synchronize_session=False)
        if version_ids:
            db.query(Acknowledgement).filter(Acknowledgement.version_id.in_(version_ids)).delete(synchronize_session=False)
        for model in (Question, Gap, Conflict, Claim, HandoverVersion, EvidenceUnit, Source, Invite, Job,
                      AuditEvent, Membership):
            db.query(model).filter_by(project_id=project_id).delete(synchronize_session=False)
        db.query(Project).filter_by(id=project_id).delete(synchronize_session=False)
        db.commit()


def _existing_project_id() -> str | None:
    from .models import Project

    with SessionLocal() as db:
        p = db.query(Project).filter_by(is_judge_demo=True).first()
        return p.id if p else None


def build() -> str:
    """Create (or re-create) the shared judge demo project. Returns its id."""
    from .demo import SEED_DIR, SEED_FILES
    from .models import LABELS, Project

    c = _client()
    h = lambda t: {"Authorization": f"Bearer {t}"}  # noqa: E731
    rev, riya, karan = (_token(c, *REVIEWER), _token(c, *LEAVER), _token(c, *NEWCOMER))
    r = c.post("/projects", headers=h(rev), json={
        "name": PROJECT_NAME,
        "description": "Synthetic demo: a college club's event registration app. Riya is leaving, Karan is taking "
                       "over, Priya reviews. Shared by all judges; anyone can reset it to the starting state.",
        "departing": {"name": LEAVER[0], "handle": "riya-dev", "access_level": "Leads"},
        "incoming": {"name": NEWCOMER[0], "handle": "karan-m", "access_level": "Leads"}})
    r.raise_for_status()
    pid = r.json()["id"]
    with SessionLocal() as db:
        db.get(Project, pid).is_judge_demo = True
        db.commit()
    for filename, label in SEED_FILES:
        r = c.post(f"/projects/{pid}/sources/upload", headers=h(rev), data={"access_label": LABELS[label]},
                   files=[("files", (filename, (SEED_DIR / filename).read_bytes()))])
        r.raise_for_status()
    c.post(f"/projects/{pid}/analyse", headers=h(rev), json={"mode": "full"}).raise_for_status()
    job = c.get(f"/projects/{pid}/jobs/latest", headers=h(rev)).json()
    if not job or job.get("status") != "done":
        raise RuntimeError(f"Analysis did not finish: {job and job.get('error')}")
    # Settle every conflict in favour of the newer evidence.
    for k in c.get(f"/projects/{pid}/conflicts", headers=h(rev)).json()["conflicts"]:
        if k["status"] != "open":
            continue
        side = k["side_b"] if k.get("newer_side") != "a" else k["side_a"]
        if side:
            c.post(f"/conflicts/{k['id']}/resolve", headers=h(rev),
                   json={"winner_claim_id": side[0]["id"], "note": "Newer evidence is current."})
    # Approve what passed the checks; reject what didn't.
    for cl in c.get(f"/projects/{pid}/claims", headers=h(rev)).json()["claims"]:
        if cl["review_state"] != "pending":
            continue
        if cl["confidence"] == "unverified":
            c.post(f"/claims/{cl['id']}/review", headers=h(rev),
                   json={"action": "reject", "reason": "Quote not found in the source."})
        else:
            c.post(f"/claims/{cl['id']}/review", headers=h(rev), json={"action": "approve"})
    v = c.post(f"/projects/{pid}/handover/generate", headers=h(rev))
    v.raise_for_status()
    c.post(f"/handover/{v.json()['id']}/approve", headers=h(rev)).raise_for_status()
    # Both people join with their own accounts through invite links.
    members = c.get(f"/projects/{pid}/members", headers=h(rev)).json()["members"]
    for name, tok in ((LEAVER[0], riya), (NEWCOMER[0], karan)):
        slot = next(m for m in members if m["name"] == name and not m["joined"])
        inv = c.post(f"/projects/{pid}/invites", headers=h(rev), json={"user_id": slot["user_id"]}).json()
        c.post(f"/invites/{inv['token']}/accept", headers=h(tok)).raise_for_status()
    return pid


def _dedupe() -> None:
    """Two server instances starting together (e.g. during a redeploy) could each build one: keep the oldest."""
    from .models import Project

    with SessionLocal() as db:
        ids = [p.id for p in db.query(Project).filter_by(is_judge_demo=True).order_by(Project.created_at)]
    for extra in ids[1:]:
        _wipe(extra)


def ensure(background: bool = True) -> None:
    """Build the judge demo once if it doesn't exist (called at start-up)."""
    if os.environ.get("BATON_SKIP_JUDGE_DEMO"):
        return

    def run():
        with _lock:
            if _existing_project_id():
                state.update(status="ready", error=None)
                return
            state.update(status="building", error=None)
            try:
                build()
                _dedupe()
                state.update(status="ready")
                log.info("Judge demo project ready.")
            except Exception as e:  # noqa: BLE001
                state.update(status="failed", error=str(e)[:300])
                log.exception("Could not build the judge demo")

    if background:
        threading.Thread(target=run, daemon=True).start()
    else:
        run()


def reset(background: bool = True) -> None:
    def run():
        with _lock:
            state.update(status="building", error=None)
            try:
                old = _existing_project_id()
                if old:
                    _wipe(old)
                build()
                state.update(status="ready")
            except Exception as e:  # noqa: BLE001
                state.update(status="failed", error=str(e)[:300])
                log.exception("Could not reset the judge demo")

    if background:
        threading.Thread(target=run, daemon=True).start()
    else:
        run()


# ---------- API ----------
from fastapi import APIRouter, Depends, HTTPException  # noqa: E402

from .auth.security import current_session  # noqa: E402

router = APIRouter(tags=["judge demo"])


@router.get("/judge-demo")
def judge_demo_info():
    """Public: the ready-made demo accounts and whether the shared project is ready."""
    pid = _existing_project_id()
    status = "ready" if pid and state["status"] != "building" else state["status"]
    return {"accounts": accounts(), "password": PASSWORD, "status": status, "error": state["error"]}


@router.post("/judge-demo/reset")
def judge_demo_reset(s=Depends(current_session)):
    """Anyone signed in to one of the demo accounts can put the shared project back to its starting state."""
    real = s.real_user
    if not real or (real.email or "") not in {a["email"] for a in accounts()}:
        raise HTTPException(403, "Only the demo accounts can reset the shared demo project.")
    if state["status"] == "building":
        return {"status": "building"}
    reset()
    return {"status": "building"}
