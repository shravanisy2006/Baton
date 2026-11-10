from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..audit.service import log as audit
from ..auth.security import CAN_MANAGE, current_session, require_member
from ..db import get_db
from ..llm.provider import ai_status
from ..models import (LABEL_BY_NAME, LABELS, ROLES, Claim, Conflict, EvidenceUnit, Gap, HandoverVersion, Job,
                      Membership, Project, Source, User)

router = APIRouter(tags=["projects"])


class ProjectIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=2000)


def _job_out(j: Job | None) -> dict | None:
    if not j:
        return None
    return {"id": j.id, "status": j.status, "stage": j.stage, "warnings": j.warnings, "error": j.error,
            "stats": j.stats, "created_at": j.created_at.isoformat(),
            "finished_at": j.finished_at.isoformat() if j.finished_at else None}


def _members(db: Session, project_id: str) -> list[dict]:
    rows = db.query(Membership).filter_by(project_id=project_id).all()
    return [{"user_id": m.user_id, "name": m.user.name, "handle": m.user.handle, "role": m.role,
             "access_level": LABELS[m.access_level]} for m in rows]


@router.get("/projects")
def list_projects(s=Depends(current_session), db: Session = Depends(get_db)):
    if not s.user:
        return []
    rows = (db.query(Project, Membership).join(Membership, Membership.project_id == Project.id)
            .filter(Membership.user_id == s.user.id, Project.account_id == s.account.id)
            .order_by(Project.created_at.desc()).all())
    return [{"id": p.id, "name": p.name, "description": p.description, "is_demo": p.is_demo,
             "role": m.role, "created_at": p.created_at.isoformat()} for p, m in rows]


@router.post("/projects")
def create_project(body: ProjectIn, s=Depends(current_session), db: Session = Depends(get_db)):
    if not s.user:
        raise HTTPException(401, "Start a workspace first.")
    p = Project(account_id=s.account.id, name=body.name.strip(), description=body.description.strip())
    db.add(p)
    db.flush()
    db.add(Membership(project_id=p.id, user_id=s.user.id, role="admin", access_level=3))
    audit(db, p.id, s.user, "project.created", "project", p.id, name=p.name)
    db.commit()
    return {"id": p.id, "name": p.name}


@router.get("/projects/{project_id}")
def project_overview(project_id: str, s=Depends(current_session), db: Session = Depends(get_db)):
    m = require_member(db, project_id, s)
    lvl = m.level
    q = lambda model: db.query(func.count()).select_from(model).filter(model.project_id == project_id)  # noqa: E731
    claims = db.query(Claim.confidence, Claim.review_state).filter(
        Claim.project_id == project_id, Claim.access_label <= lvl).all()
    job = db.query(Job).filter_by(project_id=project_id).order_by(Job.created_at.desc()).first()
    versions = db.query(HandoverVersion).filter_by(project_id=project_id).order_by(HandoverVersion.version.desc()).all()
    approved = next((v for v in versions if v.status == "approved"), None)
    sources = q(Source).scalar()
    open_gaps = q(Gap).filter(Gap.status == "open").scalar()
    open_conflicts = q(Conflict).filter(Conflict.status == "open").scalar()
    pending = sum(1 for _, r in claims if r == "pending")
    steps = [
        {"key": "connect", "label": "Connect", "done": sources > 0},
        {"key": "reconstruct", "label": "Reconstruct", "done": bool(job and job.status == "done")},
        {"key": "verify", "label": "Verify", "done": bool(job and job.status == "done") and open_conflicts == 0},
        {"key": "review", "label": "Review", "done": bool(claims) and pending == 0},
        {"key": "handover", "label": "Handover", "done": approved is not None},
    ]
    users = {u.id: u.name for u in db.query(User).filter(User.id.in_(
        [x for x in (m.project.departing_user_id, m.project.incoming_user_id) if x] or [""]))}
    return {
        "project": {"id": m.project.id, "name": m.project.name, "description": m.project.description,
                    "is_demo": m.project.is_demo,
                    "departing": users.get(m.project.departing_user_id),
                    "incoming": users.get(m.project.incoming_user_id)},
        "me": {"user_id": m.user.id, "name": m.user.name, "role": m.role, "access_level": LABELS[lvl]},
        "members": _members(db, project_id),
        "counts": {
            "sources": sources,
            "evidence": q(EvidenceUnit).scalar(),
            "claims": len(claims),
            "verified": sum(1 for c, _ in claims if c in ("verified", "corroborated")),
            "unverified": sum(1 for c, _ in claims if c == "unverified"),
            "pending_review": pending,
            "approved": sum(1 for _, r in claims if r in ("approved", "corrected")),
            "open_gaps": open_gaps,
            "open_conflicts": open_conflicts,
        },
        "steps": steps,
        "latest_job": _job_out(job),
        "handover": {"versions": len(versions), "approved_version": approved.version if approved else None},
        "ai": ai_status(),
    }


class MemberIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    handle: str | None = Field(default=None, max_length=120)
    role: str
    access_level: str = "Team"


@router.post("/projects/{project_id}/members")
def add_member(project_id: str, body: MemberIn, s=Depends(current_session), db: Session = Depends(get_db)):
    m = require_member(db, project_id, s, ("admin",))
    if body.role not in ROLES:
        raise HTTPException(422, f"Role must be one of {', '.join(ROLES)}.")
    level = LABEL_BY_NAME.get(body.access_level.lower())
    if not level:
        raise HTTPException(422, "Access level must be Team, Leads or Restricted.")
    u = User(account_id=s.account.id, name=body.name.strip(), handle=(body.handle or "").strip() or None)
    db.add(u)
    db.flush()
    db.add(Membership(project_id=project_id, user_id=u.id, role=body.role, access_level=level))
    if body.role == "departing":
        m.project.departing_user_id = u.id
    if body.role == "incoming":
        m.project.incoming_user_id = u.id
    audit(db, project_id, m.user, "member.added", "user", u.id, name=u.name, role=body.role,
          access_level=body.access_level)
    db.commit()
    return {"user_id": u.id, "name": u.name}


@router.post("/projects/{project_id}/analyse")
def analyse(project_id: str, background: BackgroundTasks, s=Depends(current_session), db: Session = Depends(get_db)):
    from ..pipeline import run_analysis

    m = require_member(db, project_id, s, CAN_MANAGE)
    running = db.query(Job).filter_by(project_id=project_id).filter(Job.status.in_(("queued", "running"))).first()
    if running:
        raise HTTPException(409, "An analysis is already running.")
    job = Job(project_id=project_id)
    db.add(job)
    db.flush()
    audit(db, project_id, m.user, "analysis.started", "job", job.id)
    db.commit()
    background.add_task(run_analysis, project_id, job.id, m.user.id)
    return _job_out(job)


@router.get("/projects/{project_id}/jobs/latest")
def latest_job(project_id: str, s=Depends(current_session), db: Session = Depends(get_db)):
    require_member(db, project_id, s)
    return _job_out(db.query(Job).filter_by(project_id=project_id).order_by(Job.created_at.desc()).first())
