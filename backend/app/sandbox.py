"""Private demo sandboxes.

Every visitor who opens the demo (one click on the website, or the published demo credentials) gets their OWN
copy of the synthetic EventApp project, so one judge can never change or reset what another judge sees.

A sandbox is a private account holding the four EventApp people. It can start in two states:
- "handed_over" (default): analysed, reviewed and handed over (version 1 approved), ready to test what
  happens next (Ask Baton, the leaver's answers, newer evidence -> version 2).
- "fresh": files loaded but not analysed, to watch the analysis run.

The handed-over state is reached by running the real pipeline and then calling the same request handlers the
website calls (resolve conflict, review, generate, approve), directly as Python functions. AI answers for the
EventApp files come from the saved real Gemini responses (seed/eventapp/llm_cache.json) when they match; anything
else calls the configured AI. Sandboxes are deleted after SANDBOX_HOURS.
"""

import hmac
import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .auth.security import Session_, token_for
from .db import SessionLocal
from .demo import create_demo
from .models import Account, Job, Project, User

log = logging.getLogger("baton.sandbox")
PASSWORD = os.environ.get("JUDGE_DEMO_PASSWORD") or "Baton-Judge-2026"
SANDBOX_HOURS = 24
# Published demo sign-ins -> the EventApp person they open as.
DEMO_LOGINS = {
    "reviewer@baton.demo": "reviewer",
    "riya@baton.demo": "departing",
    "karan@baton.demo": "incoming",
}
ROLE_NAMES = {"reviewer": "Priya Nair", "departing": "Riya Sharma", "incoming": "Karan Mehta"}


def accounts() -> list[dict]:
    return [{"role": role, "name": ROLE_NAMES[role], "email": email} for email, role in DEMO_LOGINS.items()]


def password_ok(password: str) -> bool:
    return hmac.compare_digest((password or "").encode(), PASSWORD.encode())


def _person(db: Session, project: Project, role: str) -> User:
    from .models import Membership

    m = db.query(Membership).filter_by(project_id=project.id, role=role).first()
    return m.user


def _hand_over(db: Session, project: Project, reviewer: User, account: Account) -> None:
    """Settle, review, generate and approve version 1 exactly as a reviewer would on the website."""
    from .detect.router import ResolveIn, resolve_conflict
    from .handover.router import approve, generate
    from .models import Claim, Conflict
    from .verify.router import ReviewIn, review_claim

    s = Session_(account, reviewer)
    for k in db.query(Conflict).filter_by(project_id=project.id, status="open").all():
        side = k.side_a if k.newer_side == "a" else k.side_b
        if side:
            resolve_conflict(k.id, ResolveIn(winner_claim_id=side[0], note="Newer evidence is current."), s=s, db=db)
    for c in db.query(Claim).filter_by(project_id=project.id, review_state="pending").order_by(Claim.created_at).all():
        if c.confidence == "unverified":
            review_claim(c.id, ReviewIn(action="reject", reason="Quote not found in the source."), s=s, db=db)
        else:
            review_claim(c.id, ReviewIn(action="approve"), s=s, db=db)
    v = generate(project.id, s=s, db=db)
    approve(v["id"], s=s, db=db)


def create_sandbox(as_role: str = "reviewer", stage: str = "handed_over") -> tuple[str, str]:
    """Build a private sandbox and return (session token for the chosen person, project id)."""
    from .jobs import run_job_now

    with SessionLocal() as db:
        acc = Account(kind="demo")
        db.add(acc)
        db.flush()
        project, reviewer, job = create_demo(db, acc)
        job.actor_id = reviewer.id
        db.commit()
        pid, job_id, account_id, reviewer_id = project.id, job.id, acc.id, reviewer.id
    if stage == "handed_over":
        run_job_now(job_id)
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job.status != "done":
                raise RuntimeError(job.error or "The demo analysis did not finish.")
            _hand_over(db, db.get(Project, pid), db.get(User, reviewer_id), db.get(Account, account_id))
    else:
        from .jobs import after_commit

        after_commit(job_id)
    with SessionLocal() as db:
        person = _person(db, db.get(Project, pid), as_role if as_role in ROLE_NAMES else "reviewer")
        return token_for(person), pid


def delete_account_data(db: Session, account_id: str) -> None:
    """Delete an account's projects (with everything in them), its people and the account itself."""
    from .models import Token
    from .projects.service import delete_project

    for p in db.query(Project).filter_by(account_id=account_id).all():
        delete_project(db, p.id)
    ids = [u for (u,) in db.query(User.id).filter_by(account_id=account_id)]
    if ids:
        db.query(Token).filter(Token.user_id.in_(ids)).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
    db.query(Account).filter_by(id=account_id).delete(synchronize_session=False)


def _only_demo_projects(db: Session, account_id: str) -> bool:
    return all(p.is_demo for p in db.query(Project).filter_by(account_id=account_id))


def cleanup_old_sandboxes() -> int:
    """Delete demo copies older than SANDBOX_HOURS. Legacy "guest" accounts from earlier versions are removed only
    if all they hold are demo copies, so nobody's own work is ever deleted by this. Returns how many were removed."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=SANDBOX_HOURS)
    removed = 0
    with SessionLocal() as db:
        old = [
            a
            for (a, kind) in db.query(Account.id, Account.kind).filter(
                Account.kind.in_(("demo", "guest")), Account.created_at < cutoff
            )
            if kind == "demo" or _only_demo_projects(db, a)
        ]
        for account_id in old:
            try:
                delete_account_data(db, account_id)
                db.commit()
                removed += 1
            except Exception:  # noqa: BLE001
                db.rollback()
                log.exception("Could not remove demo sandbox %s", account_id)
    removed += remove_legacy_shared_demo()
    if removed:
        log.info("Removed %d expired demo copies.", removed)
    return removed


def remove_legacy_shared_demo() -> int:
    """Earlier versions had ONE shared judge project with real accounts on the demo addresses. Demo sign-ins now
    open private copies, so that shared project and those accounts are removed once."""
    removed = 0
    with SessionLocal() as db:
        accounts_ = {u.account_id for u in db.query(User).filter(User.email.in_(list(DEMO_LOGINS)))}
        accounts_ |= {p.account_id for p in db.query(Project).filter_by(is_judge_demo=True)}
        for account_id in accounts_:
            try:
                delete_account_data(db, account_id)
                db.commit()
                removed += 1
            except Exception:  # noqa: BLE001
                db.rollback()
                log.exception("Could not remove the old shared demo (%s)", account_id)
    return removed
