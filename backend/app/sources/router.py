from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import ratelimit
from ..audit.service import log as audit
from ..auth.security import CAN_MANAGE, current_session, require_member
from ..config import get_settings
from ..db import get_db
from ..ingest.github import GitHubError, fetch_repo
from ..ingest.parsers import ParseError, kind_for, parse_file
from ..ingest.service import store_units
from ..models import LABEL_BY_NAME, Source
from ..serialize import source_out

router = APIRouter(tags=["sources"])
UNSUPPORTED = (
    "Unsupported file type. Use PDF, Word (DOCX), TXT, Markdown, CSV, JSON, a WhatsApp chat export (TXT) "
    "or an image (PNG, JPG, WEBP)."
)


def _level(name: str) -> int:
    lvl = LABEL_BY_NAME.get((name or "").strip().lower())
    if not lvl:
        raise HTTPException(422, "Access label must be Team, Leads or Restricted.")
    return lvl


@router.get("/projects/{project_id}/sources")
def list_sources(project_id: str, s=Depends(current_session), db: Session = Depends(get_db)):
    m = require_member(db, project_id, s)
    rows = db.query(Source).filter_by(project_id=project_id).order_by(Source.created_at).all()
    visible = [r for r in rows if r.access_label <= m.level and r.kind != "attestation"]
    attest = [r for r in rows if r.access_label <= m.level and r.kind == "attestation"]
    return {
        "sources": [source_out(r) for r in visible + attest],
        "hidden_count": sum(1 for r in rows if r.access_label > m.level),
    }


def _read_capped(f: UploadFile, limit: int) -> bytes | None:
    """Read at most limit+1 bytes, so an oversized upload is rejected without being held in memory."""
    data = f.file.read(limit + 1)
    return None if len(data) > limit else data


@router.post("/projects/{project_id}/sources/upload")
def upload_sources(
    project_id: str,
    files: list[UploadFile] = File(...),
    access_label: str = Form("Team"),
    s=Depends(current_session),
    db: Session = Depends(get_db),
):
    """Parse uploaded files into evidence. A plain (non-async) handler on purpose: parsing and reading scans with
    the AI are slow, blocking work, so FastAPI runs this in its thread pool and the server stays responsive.
    Original files are not kept: only the redacted evidence text is stored."""
    settings = get_settings()
    m = require_member(db, project_id, s, CAN_MANAGE)
    level = _level(access_label)
    if level > m.level:
        raise HTTPException(403, "You can't label a source above your own access level.")
    if len(files) > settings.max_files_per_upload:
        raise HTTPException(413, f"Upload at most {settings.max_files_per_upload} files at a time.")
    existing = db.query(Source).filter_by(project_id=project_id).count()
    if existing + len(files) > settings.max_sources_per_project:
        raise HTTPException(
            413, f"A project can hold at most {settings.max_sources_per_project} sources. Delete some you no longer need first."
        )
    ratelimit.hit(f"upload:{m.user.id}", 60, 600, "That's a lot of uploads in a short time. Wait a few minutes.")
    limit = settings.max_upload_mb * 1024 * 1024
    results = []
    for f in files:
        name = (f.filename or "file").split("/")[-1].split("\\")[-1][:200]
        if not kind_for(name):
            results.append({"filename": name, "ok": False, "error": UNSUPPORTED})
            continue
        data = _read_capped(f, limit)
        if data is None:
            results.append({"filename": name, "ok": False, "error": f"File is larger than {settings.max_upload_mb} MB."})
            continue
        src = Source(project_id=project_id, kind=kind_for(name), filename=name, access_label=level, authorised_by=m.user.id)
        db.add(src)
        db.flush()
        try:
            src.kind, parsed = parse_file(data, name)
            ocr_pages = len(parsed.needs_ocr)
            if ocr_pages:
                from ..ingest.ocr import transcribe

                transcribe(db, parsed, name)
            store_units(db, src, parsed)
            if ocr_pages:
                src.coverage = {**(src.coverage or {}), "ocr_pages": ocr_pages}
        except ParseError as e:
            src.status, src.error = "failed", str(e)
        audit(
            db,
            project_id,
            m.user,
            "source.uploaded",
            "source",
            src.id,
            filename=name,
            access_label=access_label,
            status=src.status,
            units=src.unit_count,
        )
        db.commit()
        results.append({"filename": name, "ok": src.status == "parsed", "source": source_out(src), "error": src.error})
    return {"results": results}


@router.post("/sources/{source_id}/delete")
def delete_source(source_id: str, s=Depends(current_session), db: Session = Depends(get_db)):
    """Delete a source and its evidence everywhere it appears: claims that relied only on it are removed,
    claims with other evidence lose its quotes and must be re-checked, and its quotes are removed from stored
    handover versions and Ask Baton answers."""
    from ..ingest.service import delete_source_everywhere

    src = db.get(Source, source_id)
    if not src:
        raise HTTPException(404, "Source not found.")
    m = require_member(db, src.project_id, s, CAN_MANAGE)
    if src.access_label > m.level:
        raise HTTPException(404, "Source not found.")
    from ..models import Job

    if db.query(Job).filter_by(project_id=src.project_id).filter(Job.status.in_(("queued", "running"))).first():
        raise HTTPException(409, "An analysis is running. Wait for it to finish, then delete.")
    summary = delete_source_everywhere(db, src)
    audit(db, src.project_id, m.user, "source.deleted", "source", source_id, filename=src.filename, **summary)
    db.commit()
    return {"deleted": source_id, **summary}


class GitHubIn(BaseModel):
    repo_url: str
    access_label: str = "Team"
    token: str | None = None


@router.post("/projects/{project_id}/sources/github")
def import_github(project_id: str, body: GitHubIn, s=Depends(current_session), db: Session = Depends(get_db)):
    m = require_member(db, project_id, s, CAN_MANAGE)
    level = _level(body.access_label)
    if level > m.level:
        raise HTTPException(403, "You can't label a source above your own access level.")
    ratelimit.hit(f"github:{m.user.id}", 10, 600)
    if db.query(Source).filter_by(project_id=project_id).count() >= get_settings().max_sources_per_project:
        raise HTTPException(413, "This project has reached its source limit. Delete some sources first.")
    try:
        full, parsed = fetch_repo(body.repo_url, body.token)
    except GitHubError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Could not reach GitHub: {e}") from e
    src = Source(
        project_id=project_id,
        kind="github",
        filename=f"GitHub · {full}",
        uri=f"https://github.com/{full}",
        access_label=level,
        authorised_by=m.user.id,
    )
    db.add(src)
    db.flush()
    store_units(db, src, parsed)
    # The token is used once and never stored.
    audit(
        db,
        project_id,
        m.user,
        "source.github_imported",
        "source",
        src.id,
        repo=full,
        units=src.unit_count,
        access_label=body.access_label,
    )
    db.commit()
    return source_out(src)
