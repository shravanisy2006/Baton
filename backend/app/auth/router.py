import re
import time
from collections import defaultdict

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Account, Membership, Project, User
from .security import Session_, check_password, current_session, hash_password, make_token

router = APIRouter(prefix="/auth", tags=["auth"])
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_failed: dict[str, list[float]] = defaultdict(list)  # email -> recent failed sign-in times


def _user_out(u: User | None) -> dict | None:
    return {"id": u.id, "name": u.name, "handle": u.handle, "email": u.email} if u else None


def _clean_email(email: str) -> str:
    e = (email or "").strip().lower()
    if not EMAIL_RE.match(e) or len(e) > 255:
        raise HTTPException(422, "Enter a valid email address.")
    return e


def _optional_session(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> Session_ | None:
    if not authorization:
        return None
    try:
        return current_session(authorization, db)
    except HTTPException:
        return None


class SignUpIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str
    password: str = Field(min_length=8, max_length=200)


class SignInIn(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=200)


@router.post("/signup")
def sign_up(body: SignUpIn, s: Session_ | None = Depends(_optional_session), db: Session = Depends(get_db)):
    """Create an account. A guest who already started a workspace keeps it: the guest becomes this account."""
    email = _clean_email(body.email)
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Enter your name.")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    upgradable = (s and s.account.kind == "guest" and s.user and not s.via and not s.user.email
                  and not db.query(Project).filter_by(account_id=s.account.id, is_demo=True).first())
    if upgradable:
        acc, user = s.account, s.user
    else:
        acc = Account(kind="user")
        db.add(acc)
        db.flush()
        user = User(account_id=acc.id, name=name)
        db.add(user)
    acc.kind, acc.email = "user", email
    user.name, user.email, user.password_hash = name, email, hash_password(body.password)
    db.commit()
    return {"token": make_token(acc.id, user.id), "user": _user_out(user)}


@router.post("/signin")
def sign_in(body: SignInIn, db: Session = Depends(get_db)):
    email = (body.email or "").strip().lower()
    recent = [t for t in _failed[email] if time.time() - t < 900]
    _failed[email] = recent
    if len(recent) >= 8:
        raise HTTPException(429, "Too many attempts. Wait 15 minutes and try again.")
    user = db.query(User).filter(User.email == email, User.merged_into.is_(None)).first() if email else None
    if not user or not check_password(body.password, user.password_hash):
        _failed[email].append(time.time())
        raise HTTPException(401, "Email or password is incorrect.")
    _failed.pop(email, None)
    return {"token": make_token(user.account_id, user.id), "user": _user_out(user)}


@router.post("/guest")
def start_guest(db: Session = Depends(get_db)):
    """A private workspace without signing up (kept for older links; new projects ask for an account)."""
    acc = Account(kind="guest")
    db.add(acc)
    db.flush()
    user = User(account_id=acc.id, name="You")
    db.add(user)
    db.commit()
    return {"token": make_token(acc.id, user.id), "user": _user_out(user)}


@router.post("/demo")
def start_demo(background: BackgroundTasks, db: Session = Depends(get_db)):
    """Create a fresh, private copy of the synthetic EventApp worked example, signed in as its reviewer."""
    from ..demo import create_demo
    from ..pipeline import run_analysis

    acc = Account(kind="guest")
    db.add(acc)
    db.flush()
    project, reviewer, job = create_demo(db, acc)
    db.commit()
    background.add_task(run_analysis, project.id, job.id, reviewer.id)
    return {"token": make_token(acc.id, reviewer.id), "user": _user_out(reviewer), "project_id": project.id}


def _previewable(db: Session, s: Session_) -> list[User]:
    """People you may preview as: in the worked example everyone; in your own projects, only people who
    haven't joined with their own account yet."""
    demo = db.query(Project).filter_by(account_id=s.account.id, is_demo=True).first() is not None
    q = db.query(User).filter(User.account_id == s.account.id, User.merged_into.is_(None))
    if not demo:
        q = q.filter(User.email.is_(None))
    real = s.real_user
    people = [u for u in q.order_by(User.created_at).all() if not real or u.id != real.id]
    return people


@router.get("/me")
def me(s=Depends(current_session), db: Session = Depends(get_db)):
    rows = (db.query(Membership, Project).join(Project, Project.id == Membership.project_id)
            .filter(Membership.user_id == s.user.id).order_by(Project.created_at.desc()).all()) if s.user else []
    real = s.real_user
    demo = db.query(Project).filter_by(account_id=s.account.id, is_demo=True).first() is not None
    return {
        "account": {"id": s.account.id, "kind": s.account.kind},
        "user": _user_out(s.user),
        "real_user": _user_out(real),
        "previewing": bool(s.via),
        "registered": s.registered,
        "is_demo": demo,
        "people": [_user_out(p) for p in (
            db.query(User).filter_by(account_id=s.account.id).order_by(User.created_at).all() if demo
            else ([real] if real else []) + _previewable(db, s))],
        "projects": [{"id": p.id, "name": p.name, "is_demo": p.is_demo, "role": m.role} for m, p in rows],
    }


class ActAs(BaseModel):
    user_id: str


@router.post("/act-as")
def act_as(body: ActAs, s=Depends(current_session), db: Session = Depends(get_db)):
    """Preview as someone who hasn't joined yet (or anyone, in the worked example), or switch back to yourself."""
    real = s.real_user
    if real and body.user_id == real.id:
        return {"token": make_token(s.account.id, real.id), "user": _user_out(real)}
    target = db.get(User, body.user_id)
    if not target or target not in _previewable(db, s):
        raise HTTPException(404, "You can only preview people who haven't joined with their own account yet.")
    demo = db.query(Project).filter_by(account_id=s.account.id, is_demo=True).first() is not None
    via = None if demo or not real or not real.email else real.id
    return {"token": make_token(s.account.id, target.id, via), "user": _user_out(target)}
