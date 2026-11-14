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


class PersonIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    handle: str | None = Field(default=None, max_length=120)
    access_level: str = "Leads"


class ProjectIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=2000)
    your_name: str | None = Field(default=None, max_length=120)
    departing: PersonIn | None = None
    incoming: PersonIn | None = None


def _job_out(j: Job | None) -> dict | None:
    if not j:
        return None
    return {"id": j.id, "kind": j.kind, "status": j.status, "stage": j.stage, "warnings": j.warnings, "error": j.error,
            "stats": j.stats, "created_at": j.created_at.isoformat(),
            "finished_at": j.finished_at.isoformat() if j.finished_at else None}


def _members(db: Session, project_id: str, me_id: str | None = None) -> list[dict]:
    from ..team.router import members_out

    return members_out(db, project_id, me_id)


@router.get("/projects")
def list_projects(s=Depends(current_session), db: Session = Depends(get_db)):
    if not s.user:
        return []
    rows = (db.query(Project, Membership).join(Membership, Membership.project_id == Project.id)
            .filter(Membership.user_id == s.user.id)
            .order_by(Project.created_at.desc()).all())
    return [{"id": p.id, "name": p.name, "description": p.description, "is_demo": p.is_demo,
             "role": m.role, "created_at": p.created_at.isoformat()} for p, m in rows]


@router.post("/projects")
def create_project(body: ProjectIn, s=Depends(current_session), db: Session = Depends(get_db)):
    if not s.user:
        raise HTTPException(401, "Sign in first.")
    if not s.registered or s.via:
        raise HTTPException(401, "Create a free account (or sign in) to hand over your own project.")
    levels = {}
    for key in ("departing", "incoming"):
        person = getattr(body, key)
        if person:
            levels[key] = LABEL_BY_NAME.get(person.access_level.lower())
            if not levels[key]:
                raise HTTPException(422, "Access level must be Team, Leads or Restricted.")
    p = Project(account_id=s.account.id, name=body.name.strip(), description=body.description.strip())
    db.add(p)
    db.flush()
    db.add(Membership(project_id=p.id, user_id=s.user.id, role="admin", access_level=3))
    audit(db, p.id, s.user, "project.created", "project", p.id, name=p.name)
    for key in ("departing", "incoming"):
        person = getattr(body, key)
        if not person or not person.name.strip():
            continue
        u = User(account_id=s.account.id, name=person.name.strip(), handle=(person.handle or "").strip() or None)
        db.add(u)
        db.flush()
        db.add(Membership(project_id=p.id, user_id=u.id, role=key, access_level=levels[key]))
        setattr(p, f"{key}_user_id", u.id)
        audit(db, p.id, s.user, "member.added", "user", u.id, name=u.name, role=key,
              access_level=LABELS[levels[key]])
    db.commit()
    return {"id": p.id, "name": p.name}


@router.get("/samples.zip", tags=["system"])
def sample_files():
    """The synthetic EventApp files, so anyone can try the upload flow without their own project data."""
    import io
    import zipfile

    from fastapi.responses import Response

    from ..demo import SEED_DIR, SEED_FILES

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for filename, label in SEED_FILES:
            z.write(SEED_DIR / filename, filename)
        z.writestr("LABELS.txt", "Suggested access label for each file when you upload it:\n" + "\n".join(
            f"{f}: {LABELS[label]}" for f, label in SEED_FILES) + "\n\nSuggested people: Riya Sharma (username riya-dev) "
            "is leaving; Karan Mehta (username karan-m) is taking over. All content is synthetic.\n")
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="baton-sample-project.zip"'})


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
    outdated = False
    if approved and "approved_claim_ids" in (approved.snapshot or {}):
        from ..handover.service import fingerprint

        current = {fingerprint(c) for c in db.query(Claim).filter(Claim.project_id == project_id,
                                                                  Claim.review_state.in_(("approved", "corrected")))}
        outdated = set(approved.snapshot["approved_claim_ids"]) != current
    users = {u.id: u.name for u in db.query(User).filter(User.id.in_(
        [x for x in (m.project.departing_user_id, m.project.incoming_user_id) if x] or [""]))}
    return {
        "project": {"id": m.project.id, "name": m.project.name, "description": m.project.description,
                    "is_demo": m.project.is_demo,
                    "departing": users.get(m.project.departing_user_id),
                    "incoming": users.get(m.project.incoming_user_id)},
        "me": {"user_id": m.user.id, "name": m.user.name, "role": m.role, "access_level": LABELS[lvl]},
        "members": _members(db, project_id, m.user.id),
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
            "new_evidence": q(EvidenceUnit).filter(EvidenceUnit.analysed_at.is_(None),
                                                   EvidenceUnit.kind != "attestation").scalar(),
            "changed_since_approval": db.query(func.count()).select_from(Claim).filter(
                Claim.project_id == project_id, Claim.changed_note.isnot(None), Claim.access_label <= lvl,
                Claim.review_state.in_(("approved", "corrected"))).scalar(),
            "github_sources": q(Source).filter(Source.kind == "github").scalar(),
        },
        "steps": steps,
        "latest_job": _job_out(job),
        "handover": {"versions": len(versions), "approved_version": approved.version if approved else None,
                     "outdated": outdated,
                     "draft_version": next((v.version for v in versions if v.status == "draft"), None)},
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


class AnalyseIn(BaseModel):
    mode: str | None = None  # "update" (only new evidence) | "full" (start over). Default: update if analysed before.


def start_job(db: Session, m, background: BackgroundTasks, mode: str) -> Job:
    from ..pipeline import run_analysis

    running = db.query(Job).filter_by(project_id=m.project.id).filter(Job.status.in_(("queued", "running"))).first()
    if running:
        raise HTTPException(409, "An analysis is already running. Wait for it to finish.")
    job = Job(project_id=m.project.id, kind="update" if mode == "update" else "analyse")
    db.add(job)
    db.flush()
    audit(db, m.project.id, m.user, "analysis.started", "job", job.id, mode=mode)
    db.commit()
    background.add_task(run_analysis, m.project.id, job.id, m.user.id)
    return job


@router.post("/projects/{project_id}/analyse")
def analyse(project_id: str, background: BackgroundTasks, body: AnalyseIn | None = None,
            s=Depends(current_session), db: Session = Depends(get_db)):
    m = require_member(db, project_id, s, CAN_MANAGE)
    analysed_before = db.query(EvidenceUnit).filter(EvidenceUnit.project_id == project_id,
                                                    EvidenceUnit.analysed_at.isnot(None)).first() is not None
    mode = (body.mode if body and body.mode else None) or ("update" if analysed_before else "full")
    if mode not in ("update", "full"):
        raise HTTPException(422, "Mode must be 'update' or 'full'.")
    if mode == "update":
        if not analysed_before:
            mode = "full"
        elif not db.query(EvidenceUnit).filter(EvidenceUnit.project_id == project_id,
                                               EvidenceUnit.analysed_at.is_(None),
                                               EvidenceUnit.kind != "attestation").first():
            raise HTTPException(409, "No new evidence since the last analysis. Upload files or re-sync GitHub first.")
    if not db.query(EvidenceUnit).filter_by(project_id=project_id).first():
        raise HTTPException(409, "No readable evidence yet. Upload at least one file first.")
    return _job_out(start_job(db, m, background, mode))


class RefreshIn(BaseModel):
    token: str | None = None


@router.post("/projects/{project_id}/check-for-changes")
def check_for_changes(project_id: str, background: BackgroundTasks, body: RefreshIn | None = None,
                      s=Depends(current_session), db: Session = Depends(get_db)):
    """Living handover: re-sync every GitHub source, then analyse only what is new."""
    from ..ingest.github import GitHubError, fetch_repo
    from ..ingest.service import append_new_units

    m = require_member(db, project_id, s, CAN_MANAGE)
    if db.query(Job).filter_by(project_id=project_id).filter(Job.status.in_(("queued", "running"))).first():
        raise HTTPException(409, "An analysis is already running. Wait for it to finish.")
    synced, warnings = [], []
    from datetime import datetime, timezone
    for src in db.query(Source).filter_by(project_id=project_id, kind="github").all():
        try:
            _, parsed = fetch_repo(src.uri or "", body.token if body else None)
            added = append_new_units(db, src, parsed)
            src.synced_at = datetime.now(timezone.utc)
            synced.append({"source": src.filename, "new_items": added})
            audit(db, project_id, m.user, "source.github_resynced", "source", src.id, new_items=added)
        except GitHubError as e:
            warnings.append(f"{src.filename}: {e}")
        except Exception as e:  # noqa: BLE001
            warnings.append(f"{src.filename}: could not reach GitHub ({str(e)[:120]})")
    db.commit()
    new_units = db.query(EvidenceUnit).filter(EvidenceUnit.project_id == project_id,
                                             EvidenceUnit.analysed_at.is_(None),
                                             EvidenceUnit.kind != "attestation").count()
    job = None
    if new_units:
        analysed_before = db.query(EvidenceUnit).filter(EvidenceUnit.project_id == project_id,
                                                        EvidenceUnit.analysed_at.isnot(None)).first() is not None
        job = start_job(db, m, background, "update" if analysed_before else "full")
    return {"synced": synced, "warnings": warnings, "new_evidence": new_units, "job": _job_out(job)}


@router.get("/projects/{project_id}/jobs/latest")
def latest_job(project_id: str, s=Depends(current_session), db: Session = Depends(get_db)):
    require_member(db, project_id, s)
    return _job_out(db.query(Job).filter_by(project_id=project_id).order_by(Job.created_at.desc()).first())
