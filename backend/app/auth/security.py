"""Sessions, passwords and permission checks.

A session token names an *account* and the *user* acting. Signed-up people have their own account, email and
password. People a reviewer names (the leaver, the new member) start as records in the reviewer's account; until
they accept an invite and sign in themselves, the reviewer may *preview* as them, and every audit entry made that
way says so. Project access is decided only by membership, and `require_member` returns the member's access level,
which filters Team / Leads / Restricted content in every query.
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import Account, Membership, Project, User

ALGO = "HS256"
TOKEN_DAYS = 14


# ---------- passwords (scrypt, standard library) ----------
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def check_password(password: str, stored: str | None) -> bool:
    if not stored or not stored.startswith("scrypt$"):
        return False
    _, salt, digest = stored.split("$")
    test = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1, dklen=32)
    return hmac.compare_digest(test.hex(), digest)


def make_token(account_id: str, user_id: str | None, via: str | None = None) -> str:
    payload = {
        "acc": account_id,
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_DAYS),
        "iss": "baton",
    }
    if via:
        payload["via"] = via
    return jwt.encode(payload, get_settings().app_secret, algorithm=ALGO)


class Session_:
    def __init__(self, account: Account, user: User | None, via: User | None = None):
        self.account = account
        self.user = user
        self.via = via  # the signed-in person when previewing as someone who hasn't joined yet

    @property
    def real_user(self) -> User | None:
        return self.via or self.user

    @property
    def registered(self) -> bool:
        return bool(self.real_user and self.real_user.email)


def current_session(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> Session_:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Not signed in.")
    token = authorization.split(" ", 1)[1].strip()
    try:
        data = jwt.decode(token, get_settings().app_secret, algorithms=[ALGO], options={"require": ["exp"]})
    except jwt.PyJWTError:
        raise HTTPException(401, "Your session has expired. Please sign in again.") from None
    account = db.get(Account, data.get("acc"))
    if not account:
        raise HTTPException(401, "Session no longer exists. Please sign in again.")
    user = db.get(User, data["sub"]) if data.get("sub") else None
    if user and user.account_id != account.id:
        raise HTTPException(401, "Invalid session.")
    via = db.get(User, data["via"]) if data.get("via") else None
    if user and user.merged_into:
        # This person has since joined with their own account: previews of them end here.
        if via:
            user = via
            via = None
        else:
            raise HTTPException(401, "This person now signs in with their own account.")
    if via:
        if via.account_id != account.id:
            raise HTTPException(401, "Invalid session.")
        user._audit_name = f"{via.name} (previewing as {user.name})"  # type: ignore[attr-defined]
        user._audit_id = via.id  # type: ignore[attr-defined]
    return Session_(account, user, via)


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
    m = (db.query(Membership).filter_by(project_id=project_id, user_id=session.user.id).first()
         if project and session.user else None)
    # Same 404 whether the project is missing or you aren't in it: no existence leaks.
    if not m:
        raise HTTPException(404, "Project not found, or you don't have access to it.")
    if roles and m.role not in roles:
        raise HTTPException(403, f"This action needs one of these roles: {', '.join(roles)}. You are {m.role}.")
    return Member(project, m, session.user)


CAN_MANAGE = ("admin", "reviewer")
CAN_REVIEW = ("admin", "reviewer")
CAN_SEE_WORKING = ("admin", "reviewer", "departing")  # raw evidence, draft claims, gaps
