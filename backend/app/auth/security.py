"""Sessions and permission checks.

A session token names an *account* (the browser session's owner) and the *user* it is currently
acting as. Users (personas) always belong to one account, so you can only act as people inside
your own workspaces. Every project query goes through `require_member`, which also returns the
member's access level used to filter Team / Leads / Restricted content in SQL.
"""
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import Account, Membership, Project, User

ALGO = "HS256"
TOKEN_DAYS = 7


def make_token(account_id: str, user_id: str | None) -> str:
    payload = {
        "acc": account_id,
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_DAYS),
        "iss": "baton",
    }
    return jwt.encode(payload, get_settings().app_secret, algorithm=ALGO)


class Session_:
    def __init__(self, account: Account, user: User | None):
        self.account = account
        self.user = user


def _from_supabase(token: str, db: Session) -> Session_ | None:
    secret = get_settings().supabase_jwt_secret
    if not secret:
        return None
    try:
        claims = jwt.decode(token, secret, algorithms=[ALGO], audience="authenticated")
    except jwt.PyJWTError:
        return None
    email = claims.get("email")
    acc = db.query(Account).filter_by(kind="supabase", email=email).first()
    if not acc:
        acc = Account(kind="supabase", email=email)
        db.add(acc)
        db.flush()
        db.add(User(account_id=acc.id, name=(email or "Me").split("@")[0]))
        db.commit()
    user = db.query(User).filter_by(account_id=acc.id).order_by(User.created_at).first()
    return Session_(acc, user)


def current_session(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> Session_:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Not signed in. Open the demo or start a workspace first.")
    token = authorization.split(" ", 1)[1].strip()
    try:
        data = jwt.decode(token, get_settings().app_secret, algorithms=[ALGO], options={"require": ["exp"]})
    except jwt.PyJWTError:
        s = _from_supabase(token, db)
        if s:
            return s
        raise HTTPException(401, "Session expired or invalid. Please start again.")
    account = db.get(Account, data.get("acc"))
    if not account:
        raise HTTPException(401, "Session no longer exists.")
    user = db.get(User, data["sub"]) if data.get("sub") else None
    if user and user.account_id != account.id:
        raise HTTPException(401, "Invalid session.")
    return Session_(account, user)


class Member:
    def __init__(self, project: Project, membership: Membership, user: User):
        self.project = project
        self.membership = membership
        self.user = user

    @property
    def role(self) -> str:
        return self.membership.role

    @property
    def level(self) -> int:
        return self.membership.access_level


def require_member(db: Session, project_id: str, session: Session_, roles: tuple[str, ...] | None = None) -> Member:
    project = db.get(Project, project_id)
    # Same 404 whether the project is missing or belongs to someone else: no existence leaks.
    if not project or project.account_id != session.account.id or not session.user:
        raise HTTPException(404, "Project not found.")
    m = db.query(Membership).filter_by(project_id=project_id, user_id=session.user.id).first()
    if not m:
        raise HTTPException(403, f"{session.user.name} is not a member of this project.")
    if roles and m.role not in roles:
        raise HTTPException(403, f"This action needs one of these roles: {', '.join(roles)}. You are {m.role}.")
    return Member(project, m, session.user)


CAN_MANAGE = ("admin", "reviewer")
CAN_REVIEW = ("admin", "reviewer")
CAN_SEE_WORKING = ("admin", "reviewer", "departing")  # raw evidence, draft claims, gaps
