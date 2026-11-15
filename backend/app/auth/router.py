import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import ratelimit
from ..config import get_settings
from ..db import get_db
from ..models import Account, Membership, Project, Token, User
from ..notify import email as mail
from .security import Session_, check_password, current_session, hash_password, token_for

router = APIRouter(prefix="/auth", tags=["auth"])
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 8


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


def _registered(s: Session_) -> User:
    if s.via or not s.registered:
        raise HTTPException(403, "Sign in with your own account to do this.")
    return s.real_user


def _new_token(db: Session, user: User, kind: str, hours: int) -> str:
    raw = secrets.token_urlsafe(24)
    db.add(
        Token(
            user_id=user.id,
            kind=kind,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=hours),
        )
    )
    return raw


def _use_token(db: Session, raw: str, kind: str) -> User:
    t = db.query(Token).filter_by(token_hash=hashlib.sha256((raw or "").encode()).hexdigest(), kind=kind).first()
    exp = t.expires_at.replace(tzinfo=timezone.utc) if t and t.expires_at.tzinfo is None else (t.expires_at if t else None)
    if not t or t.used_at or exp < datetime.now(timezone.utc):
        raise HTTPException(400, "This link is invalid or has expired. Ask for a new one.")
    t.used_at = datetime.now(timezone.utc)
    user = db.get(User, t.user_id)
    if not user or user.deleted_at:
        raise HTTPException(400, "This link is invalid or has expired. Ask for a new one.")
    return user


def _send_verification(db: Session, user: User) -> str:
    raw = _new_token(db, user, "verify", 48)
    return mail.send(
        db,
        user.email,
        "Confirm your email for Baton",
        f"Hi {user.name},\n\nConfirm this is your email address:\n{mail.link('/verify/' + raw)}\n\n"
        f"The link works for 48 hours." + mail.FOOTER,
        "verify",
    )


# ---------- sign up / sign in ----------
class SignUpIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str
    password: str = Field(min_length=MIN_PASSWORD, max_length=200)


class SignInIn(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=200)


@router.post("/signup")
def sign_up(body: SignUpIn, request: Request, db: Session = Depends(get_db)):
    ratelimit.hit(
        f"signup:{ratelimit.client_ip(request)}", 10, 3600, "Too many new accounts from this network. Try again in an hour."
    )
    email = _clean_email(body.email)
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Enter your name.")
    from ..sandbox import DEMO_LOGINS

    if email in DEMO_LOGINS or email.endswith("@baton.demo"):
        raise HTTPException(409, "That address is reserved for the demo. Use your own email.")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    acc = Account(kind="user", email=email)
    db.add(acc)
    db.flush()
    user = User(account_id=acc.id, name=name, email=email, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError:  # two sign-ups with the same email at the same moment: the database enforces it
        db.rollback()
        raise HTTPException(409, "An account with this email already exists. Sign in instead.") from None
    email_status = _send_verification(db, user) if get_settings().email_configured else "not_configured"
    db.commit()
    return {"token": token_for(user), "user": _user_out(user), "verification_email": email_status}


@router.post("/signin")
def sign_in(body: SignInIn, request: Request, s: Session_ | None = Depends(_optional_session), db: Session = Depends(get_db)):
    from ..sandbox import DEMO_LOGINS, password_ok

    ip = ratelimit.client_ip(request)
    email = (body.email or "").strip().lower()
    # Limits are per network address: failing on purpose can't lock anyone else out of their account.
    ratelimit.hit(f"signin-ip:{ip}", 40, 900, "Too many sign-in attempts from this network. Wait 15 minutes.")
    fail_key = f"signin-fail:{ip}:{email}"
    if ratelimit.count(fail_key, 900) >= 8:
        raise HTTPException(429, "Too many wrong passwords for this email from this network. Wait 15 minutes.")

    if email in DEMO_LOGINS:
        if not password_ok(body.password):
            ratelimit.record(fail_key)
            raise HTTPException(401, "Email or password is incorrect.")
        return _demo_sign_in(DEMO_LOGINS[email], request, s, db)

    user = (
        db.query(User).filter(User.email == email, User.merged_into.is_(None), User.deleted_at.is_(None)).first()
        if email
        else None
    )
    if not user or not check_password(body.password, user.password_hash):
        ratelimit.record(fail_key)
        raise HTTPException(401, "Email or password is incorrect.")
    ratelimit.clear(fail_key)
    return {"token": token_for(user), "user": _user_out(user)}


# ---------- private demo sandboxes ----------
class DemoIn(BaseModel):
    role: str = Field(default="reviewer", pattern="^(reviewer|departing|incoming)$")
    stage: str = Field(default="handed_over", pattern="^(handed_over|fresh)$")


def _demo_rate(request: Request) -> None:
    ratelimit.hit(
        f"demo:{ratelimit.client_ip(request)}",
        12,
        3600,
        "You've opened many demo copies from this network. Try again in an hour.",
    )
    ratelimit.hit("demo:global", 600, 86400, "The demo is very busy today. Please try again later.")


def _sandbox_person(db: Session, account_id: str, role: str) -> User | None:
    project = db.query(Project).filter_by(account_id=account_id, is_demo=True).first()
    if not project:
        return None
    m = db.query(Membership).filter_by(project_id=project.id, role=role).first()
    return m.user if m else None


def _demo_sign_in(role: str, request: Request, s: Session_ | None, db: Session) -> dict:
    """Demo credentials always open a PRIVATE copy. If this browser already has one, switch person inside it,
    so a judge can play the reviewer, then the leaver, then the new member in the same world."""
    from ..sandbox import create_sandbox

    if s and s.account.kind == "demo":
        person = _sandbox_person(db, s.account.id, role)
        if person:
            return {"token": token_for(person), "user": _user_out(person), "sandbox": "existing"}
    _demo_rate(request)
    token, pid = create_sandbox(role, "handed_over")
    return {"token": token, "project_id": pid, "sandbox": "new"}


@router.post("/demo")
def start_demo(request: Request, body: DemoIn | None = None):
    """Create a private demo copy for this visitor and sign in as the chosen EventApp person."""
    from ..sandbox import create_sandbox

    body = body or DemoIn()
    _demo_rate(request)
    try:
        token, pid = create_sandbox(body.role, body.stage)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            503, f"The demo couldn't be prepared right now. Please try again in a minute. ({str(e)[:160]})"
        ) from e
    return {"token": token, "project_id": pid}


@router.post("/demo/restart")
def restart_demo(request: Request, s=Depends(current_session), db: Session = Depends(get_db)):
    """Throw this private demo copy away and start a fresh one (as the same person)."""
    from ..sandbox import create_sandbox, delete_account_data

    if s.account.kind != "demo":
        raise HTTPException(409, "Only a demo copy can be restarted.")
    role = next((m.role for m in db.query(Membership).filter_by(user_id=s.user.id)), "reviewer")
    _demo_rate(request)
    token, pid = create_sandbox(role if role in ("reviewer", "departing", "incoming") else "reviewer", "handed_over")
    delete_account_data(db, s.account.id)
    db.commit()
    return {"token": token, "project_id": pid}


# ---------- who am I, previews ----------
def _previewable(db: Session, s: Session_) -> list[User]:
    """People you may preview as: in a demo copy everyone; in your own projects, only people who haven't
    joined with their own account yet."""
    demo = s.account.kind == "demo"
    q = db.query(User).filter(User.account_id == s.account.id, User.merged_into.is_(None))
    if not demo:
        q = q.filter(User.email.is_(None))
    real = s.real_user
    return [u for u in q.order_by(User.created_at).all() if not real or u.id != real.id]


@router.get("/me")
def me(s=Depends(current_session), db: Session = Depends(get_db)):
    rows = (
        (
            db.query(Membership, Project)
            .join(Project, Project.id == Membership.project_id)
            .filter(Membership.user_id == s.user.id)
            .order_by(Project.created_at.desc())
            .all()
        )
        if s.user
        else []
    )
    real = s.real_user
    demo = s.account.kind == "demo"
    return {
        "account": {"id": s.account.id, "kind": s.account.kind},
        "user": _user_out(s.user),
        "real_user": _user_out(real),
        "previewing": bool(s.via),
        "registered": s.registered,
        "is_demo": demo,
        "email_verified": bool(real and real.email_verified_at),
        "email_configured": get_settings().email_configured,
        "people": [
            _user_out(p)
            for p in (
                db.query(User).filter_by(account_id=s.account.id).order_by(User.created_at).all()
                if demo
                else ([real] if real else []) + _previewable(db, s)
            )
        ],
        "projects": [{"id": p.id, "name": p.name, "is_demo": p.is_demo, "role": m.role} for m, p in rows],
    }


class ActAs(BaseModel):
    user_id: str


@router.post("/act-as")
def act_as(body: ActAs, s=Depends(current_session), db: Session = Depends(get_db)):
    """Preview as someone who hasn't joined yet (or anyone, in a demo copy), or switch back to yourself."""
    real = s.real_user
    if real and body.user_id == real.id:
        return {"token": token_for(real), "user": _user_out(real)}
    target = db.get(User, body.user_id)
    if not target or target not in _previewable(db, s):
        raise HTTPException(404, "You can only preview people who haven't joined with their own account yet.")
    via = None if s.account.kind == "demo" or not real or not real.email else real
    return {"token": token_for(target, via), "user": _user_out(target)}


# ---------- sessions, password, email ----------
@router.post("/signout-everywhere")
def sign_out_everywhere(s=Depends(current_session), db: Session = Depends(get_db)):
    """End every session of this account, on every device (including this one)."""
    user = _registered(s)
    user.session_version = (user.session_version or 0) + 1
    db.commit()
    return {"ok": True}


class PasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=MIN_PASSWORD, max_length=200)


@router.post("/password")
def change_password(body: PasswordIn, request: Request, s=Depends(current_session), db: Session = Depends(get_db)):
    user = _registered(s)
    ratelimit.hit(f"password:{user.id}", 10, 900)
    if not check_password(body.current_password, user.password_hash):
        raise HTTPException(401, "Your current password is incorrect.")
    user.password_hash = hash_password(body.new_password)
    user.session_version = (user.session_version or 0) + 1  # other devices are signed out
    db.commit()
    return {"token": token_for(user)}


@router.post("/verify/send")
def resend_verification(s=Depends(current_session), db: Session = Depends(get_db)):
    user = _registered(s)
    ratelimit.hit(f"verify-send:{user.id}", 5, 3600)
    if user.email_verified_at:
        return {"status": "already_verified"}
    if not get_settings().email_configured:
        raise HTTPException(503, "Email isn't set up on this server, so verification emails can't be sent.")
    status = _send_verification(db, user)
    db.commit()
    return {"status": status}


class TokenIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


@router.post("/verify")
def verify_email(body: TokenIn, db: Session = Depends(get_db)):
    user = _use_token(db, body.token, "verify")
    user.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "email": user.email}


class ResetRequestIn(BaseModel):
    email: str


@router.post("/password-reset/request")
def request_password_reset(body: ResetRequestIn, request: Request, db: Session = Depends(get_db)):
    """Always answers the same way, so it can't be used to discover which emails have accounts."""
    ratelimit.hit(f"reset:{ratelimit.client_ip(request)}", 5, 3600)
    if not get_settings().email_configured:
        raise HTTPException(
            503,
            "Password reset needs email, which isn't set up on this server. "
            "Ask the person who runs this Baton server to reset it.",
        )
    email = (body.email or "").strip().lower()
    user = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first() if email else None
    if user:
        raw = _new_token(db, user, "reset", 2)
        mail.send(
            db,
            user.email,
            "Reset your Baton password",
            f"Hi {user.name},\n\nSomeone asked to reset your Baton password. If it was you, open:\n"
            f"{mail.link('/reset-password/' + raw)}\n\nThe link works for 2 hours. If it wasn't you, "
            f"ignore this email." + mail.FOOTER,
            "password_reset",
        )
        db.commit()
    return {"ok": True}


class ResetIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    new_password: str = Field(min_length=MIN_PASSWORD, max_length=200)


@router.post("/password-reset")
def reset_password(body: ResetIn, db: Session = Depends(get_db)):
    user = _use_token(db, body.token, "reset")
    user.password_hash = hash_password(body.new_password)
    user.session_version = (user.session_version or 0) + 1
    user.email_verified_at = user.email_verified_at or datetime.now(timezone.utc)  # they received the email
    db.commit()
    return {"token": token_for(user), "user": _user_out(user)}


# ---------- delete account ----------
class DeleteAccountIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)


@router.post("/delete-account")
def delete_account(body: DeleteAccountIn, s=Depends(current_session), db: Session = Depends(get_db)):
    """Delete your account. Projects you created are deleted with everything in them. In other people's
    projects your access is removed; their audit log keeps the entries you made, under 'Deleted user'."""
    from ..audit.service import log as audit
    from ..projects.service import delete_project

    user = _registered(s)
    if not check_password(body.password, user.password_hash):
        raise HTTPException(401, "Your password is incorrect.")
    others = (
        db.query(Membership)
        .join(Project, Project.id == Membership.project_id)
        .filter(Membership.user_id == user.id, Project.account_id != user.account_id)
        .all()
    )
    for m in others:
        if m.role == "admin" and db.query(Membership).filter_by(project_id=m.project_id, role="admin").count() <= 1:
            raise HTTPException(
                409, f"You are the only admin of “{m.project.name}”, which someone else created. Make another member admin first."
            )
    owned = [p.id for p in db.query(Project).filter_by(account_id=user.account_id)]
    for pid in owned:
        delete_project(db, pid)
    for m in others:
        audit(db, m.project_id, user, "member.left", "user", user.id, note="account deleted")
        db.delete(m)
    # Named people in deleted projects who never joined are removed too.
    db.query(User).filter(User.account_id == user.account_id, User.id != user.id, User.email.is_(None)).delete(
        synchronize_session=False
    )
    db.query(Token).filter_by(user_id=user.id).delete()
    user.name, user.email, user.handle, user.password_hash = "Deleted user", None, None, None
    user.deleted_at = datetime.now(timezone.utc)
    user.session_version = (user.session_version or 0) + 1
    acc = db.get(Account, user.account_id)
    acc.email = None
    db.commit()
    return {"deleted": True, "projects_deleted": len(owned)}


@router.get("/demo/info")
def demo_info():
    """Public: the demo sign-ins shown on the website. Each sign-in opens a private copy."""
    from ..sandbox import PASSWORD, SANDBOX_HOURS, accounts

    return {"accounts": accounts(), "password": PASSWORD, "private": True, "kept_hours": SANDBOX_HOURS}
