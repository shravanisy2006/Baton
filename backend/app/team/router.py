"""Team: invite links, joining with your own account, and removing access.

The reviewer names the leaver and the new member when creating a project. Each gets a one-time invite link
(valid 14 days, stored only as a hash). Opening it and signing in moves that person's place in the project to
their own account: from then on they sign in themselves, nobody can preview as them, and the audit log records
their real name. Removing someone ends their access immediately.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..audit.service import log as audit
from ..auth.security import CAN_MANAGE, current_session, require_member
from ..db import get_db
from ..models import LABELS, Acknowledgement, Invite, Membership, Project, Question, User

router = APIRouter(tags=["team"])
INVITE_DAYS = 14


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _aware(d: datetime | None) -> datetime | None:
    return d.replace(tzinfo=timezone.utc) if d and d.tzinfo is None else d


def invite_state(i: Invite) -> str:
    if i.revoked_at:
        return "revoked"
    if i.accepted_at:
        return "accepted"
    if _aware(i.expires_at) < datetime.now(timezone.utc):
        return "expired"
    return "pending"


def _invite_out(i: Invite) -> dict:
    return {"id": i.id, "user_id": i.user_id, "role": i.role, "access_level": LABELS[i.access_level],
            "state": invite_state(i), "email_hint": i.email_hint, "created_at": i.created_at.isoformat(),
            "expires_at": _aware(i.expires_at).isoformat()}


def members_out(db: Session, project_id: str, me_id: str | None = None) -> list[dict]:
    rows = db.query(Membership).filter_by(project_id=project_id).all()
    invites = db.query(Invite).filter_by(project_id=project_id).order_by(Invite.created_at.desc()).all()
    out = []
    for m in rows:
        pending = next((i for i in invites if i.user_id == m.user_id and invite_state(i) == "pending"), None)
        joined = bool(m.user.email)
        out.append({"user_id": m.user_id, "name": m.user.name, "handle": m.user.handle, "role": m.role,
                    "access_level": LABELS[m.access_level], "joined": joined, "is_you": m.user_id == me_id,
                    "status": "joined" if joined else ("invited" if pending else "not_invited"),
                    "invite": _invite_out(pending) if pending else None})
    return out


@router.get("/projects/{project_id}/members")
def list_members(project_id: str, s=Depends(current_session), db: Session = Depends(get_db)):
    m = require_member(db, project_id, s)
    return {"members": members_out(db, project_id, m.user.id)}


class InviteIn(BaseModel):
    user_id: str
    email: str | None = Field(default=None, max_length=255)


@router.post("/projects/{project_id}/invites")
def create_invite(project_id: str, body: InviteIn, s=Depends(current_session), db: Session = Depends(get_db)):
    """Make a one-time join link for a named person. Any earlier pending link for them stops working."""
    m = require_member(db, project_id, s, CAN_MANAGE)
    if m.project.is_demo:
        raise HTTPException(409, "The worked example is a demo. Invite people from your own project.")
    target = db.query(Membership).filter_by(project_id=project_id, user_id=body.user_id).first()
    if not target:
        raise HTTPException(404, "That person is not in this project.")
    if target.user.email:
        raise HTTPException(409, f"{target.user.name} has already joined with their own account.")
    now = datetime.now(timezone.utc)
    for old in db.query(Invite).filter_by(project_id=project_id, user_id=body.user_id).all():
        if invite_state(old) == "pending":
            old.revoked_at = now
    token = secrets.token_urlsafe(24)
    inv = Invite(project_id=project_id, user_id=body.user_id, token_hash=_hash(token), role=target.role,
                 access_level=target.access_level, email_hint=(body.email or "").strip() or None,
                 created_by=s.real_user.id, expires_at=now + timedelta(days=INVITE_DAYS))
    db.add(inv)
    db.flush()
    audit(db, project_id, m.user, "invite.created", "user", body.user_id, name=target.user.name, role=target.role)
    db.commit()
    return {**_invite_out(inv), "token": token, "path": f"/invite/{token}", "name": target.user.name,
            "project": m.project.name}


@router.post("/invites/{invite_id}/revoke")
def revoke_invite(invite_id: str, s=Depends(current_session), db: Session = Depends(get_db)):
    inv = db.get(Invite, invite_id)
    if not inv:
        raise HTTPException(404, "Invite not found.")
    m = require_member(db, inv.project_id, s, CAN_MANAGE)
    if invite_state(inv) == "pending":
        inv.revoked_at = datetime.now(timezone.utc)
        audit(db, inv.project_id, m.user, "invite.revoked", "user", inv.user_id)
        db.commit()
    return _invite_out(inv)


def _find(db: Session, token: str) -> Invite:
    inv = db.query(Invite).filter_by(token_hash=_hash(token or "")).first()
    if not inv:
        raise HTTPException(404, "This invite link is not valid. Ask the reviewer for a new one.")
    return inv


@router.get("/invites/{token}")
def preview_invite(token: str, db: Session = Depends(get_db)):
    """Public: what this link is for, so the person knows what they're joining before signing in."""
    inv = _find(db, token)
    p = db.get(Project, inv.project_id)
    person = db.get(User, inv.user_id)
    inviter = db.get(User, inv.created_by) if inv.created_by else None
    return {"state": invite_state(inv), "project": p.name if p else "", "name": person.name if person else "",
            "role": inv.role, "access_level": LABELS[inv.access_level],
            "invited_by": inviter.name if inviter else None, "expires_at": _aware(inv.expires_at).isoformat()}


@router.post("/invites/{token}/accept")
def accept_invite(token: str, s=Depends(current_session), db: Session = Depends(get_db)):
    """Join the project with your own account, taking over the place the reviewer created for you."""
    inv = _find(db, token)
    state = invite_state(inv)
    if state != "pending":
        raise HTTPException(409, {"revoked": "This invite was cancelled. Ask the reviewer for a new link.",
                                  "expired": "This invite has expired. Ask the reviewer for a new link.",
                                  "accepted": "This invite has already been used."}[state])
    if s.via or not s.registered:
        raise HTTPException(401, "Sign in or create an account first, then open the link again.")
    me = s.user
    placeholder = db.get(User, inv.user_id)
    slot = db.query(Membership).filter_by(project_id=inv.project_id, user_id=inv.user_id).first()
    if not slot or not placeholder:
        raise HTTPException(409, "Your place in this project was removed. Ask the reviewer for a new link.")
    if db.query(Membership).filter_by(project_id=inv.project_id, user_id=me.id).first():
        raise HTTPException(409, "You are already a member of this project with this account.")
    project = db.get(Project, inv.project_id)
    slot.user_id = me.id
    if not me.handle and placeholder.handle:
        me.handle = placeholder.handle
    if project.departing_user_id == placeholder.id:
        project.departing_user_id = me.id
    if project.incoming_user_id == placeholder.id:
        project.incoming_user_id = me.id
    db.query(Acknowledgement).filter_by(user_id=placeholder.id).update({"user_id": me.id})
    db.query(Question).filter_by(asked_by=placeholder.id).update({"asked_by": me.id})
    placeholder.merged_into = me.id
    inv.accepted_at, inv.accepted_by = datetime.now(timezone.utc), me.id
    audit(db, inv.project_id, me, "invite.accepted", "user", me.id, name=me.name, as_person=placeholder.name,
          role=slot.role)
    db.commit()
    return {"project_id": inv.project_id, "role": slot.role}


@router.post("/projects/{project_id}/members/{user_id}/remove")
def remove_member(project_id: str, user_id: str, s=Depends(current_session), db: Session = Depends(get_db)):
    """Take someone's access away (e.g. the leaver once the handover is done). Their past actions stay in the log."""
    m = require_member(db, project_id, s, ("admin",))
    target = db.query(Membership).filter_by(project_id=project_id, user_id=user_id).first()
    if not target:
        raise HTTPException(404, "That person is not in this project.")
    if target.user_id == m.user.id or (s.real_user and target.user_id == s.real_user.id):
        raise HTTPException(409, "You can't remove yourself.")
    if target.role == "admin" and db.query(Membership).filter_by(project_id=project_id, role="admin").count() <= 1:
        raise HTTPException(409, "A project needs at least one admin.")
    now = datetime.now(timezone.utc)
    for inv in db.query(Invite).filter_by(project_id=project_id, user_id=user_id).all():
        if invite_state(inv) == "pending":
            inv.revoked_at = now
    name, role = target.user.name, target.role
    db.delete(target)
    audit(db, project_id, m.user, "member.removed", "user", user_id, name=name, role=role)
    db.commit()
    return {"removed": user_id}
