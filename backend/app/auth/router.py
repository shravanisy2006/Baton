from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Account, Membership, Project, User
from .security import current_session, make_token

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(u: User | None) -> dict | None:
    return {"id": u.id, "name": u.name, "handle": u.handle} if u else None


@router.post("/guest")
def start_guest(db: Session = Depends(get_db)):
    """Start a private workspace without signing up. Data is isolated to this session's account."""
    acc = Account(kind="guest")
    db.add(acc)
    db.flush()
    user = User(account_id=acc.id, name="You")
    db.add(user)
    db.commit()
    return {"token": make_token(acc.id, user.id), "user": _user_out(user)}


@router.post("/demo")
def start_demo(background: BackgroundTasks, db: Session = Depends(get_db)):
    """Create a fresh, private copy of the synthetic EventApp demo and sign in as its reviewer."""
    from ..demo import create_demo
    from ..pipeline import run_analysis

    acc = Account(kind="guest")
    db.add(acc)
    db.flush()
    project, reviewer, job = create_demo(db, acc)
    db.commit()
    background.add_task(run_analysis, project.id, job.id, reviewer.id)
    return {"token": make_token(acc.id, reviewer.id), "user": _user_out(reviewer), "project_id": project.id}


@router.get("/me")
def me(s=Depends(current_session), db: Session = Depends(get_db)):
    people = db.query(User).filter_by(account_id=s.account.id).order_by(User.created_at).all()
    rows = (db.query(Membership, Project).join(Project, Project.id == Membership.project_id)
            .filter(Membership.user_id == s.user.id).all()) if s.user else []
    return {
        "account": {"id": s.account.id, "kind": s.account.kind},
        "user": _user_out(s.user),
        "people": [_user_out(p) for p in people],
        "projects": [{"id": p.id, "name": p.name, "is_demo": p.is_demo, "role": m.role} for m, p in rows],
    }


class ActAs(BaseModel):
    user_id: str


@router.post("/act-as")
def act_as(body: ActAs, s=Depends(current_session), db: Session = Depends(get_db)):
    """Switch to another person in your own workspace (e.g. view as the incoming member)."""
    target = db.get(User, body.user_id)
    if not target or target.account_id != s.account.id:
        raise HTTPException(404, "That person is not in your workspace.")
    return {"token": make_token(s.account.id, target.id), "user": _user_out(target)}
