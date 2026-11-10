from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..audit.service import log as audit
from ..auth.security import CAN_MANAGE, current_session, require_member
from ..config import get_settings
from ..db import get_db
from ..ingest.github import GitHubError, fetch_repo
from ..ingest.parsers import ParseError, kind_for, parse_file
from ..ingest.service import store_units
from ..ingest.storage import save_raw
from ..models import LABEL_BY_NAME, Source
from ..serialize import source_out

router = APIRouter(tags=["sources"])


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
    return {"sources": [source_out(r) for r in visible + attest],
            "hidden_count": sum(1 for r in rows if r.access_label > m.level)}


@router.post("/projects/{project_id}/sources/upload")
async def upload_sources(project_id: str, files: list[UploadFile] = File(...), access_label: str = Form("Team"),
                         s=Depends(current_session), db: Session = Depends(get_db)):
    m = require_member(db, project_id, s, CAN_MANAGE)
    level = _level(access_label)
    if level > m.level:
        raise HTTPException(403, "You can't label a source above your own access level.")
    limit = get_settings().max_upload_mb * 1024 * 1024
    results = []
    for f in files:
        name = (f.filename or "file").split("/")[-1].split("\\")[-1]
        data = await f.read()
        if not kind_for(name):
            results.append({"filename": name, "ok": False, "error": "Unsupported file type. Use PDF, DOCX, TXT, MD, CSV or JSON."})
            continue
        if len(data) > limit:
            results.append({"filename": name, "ok": False, "error": f"File is larger than {get_settings().max_upload_mb} MB."})
            continue
        src = Source(project_id=project_id, kind=kind_for(name), filename=name, access_label=level,
                     authorised_by=m.user.id)
        db.add(src)
        db.flush()
        try:
            src.storage_path = save_raw(project_id, src.id, name, data)
        except Exception as e:  # noqa: BLE001 — storage failure should not lose the parse
            src.storage_path = None
            src.coverage = {"storage_error": str(e)[:200]}
        try:
            src.kind, parsed = parse_file(data, name)
            store_units(db, src, parsed)
        except ParseError as e:
            src.status, src.error = "failed", str(e)
        audit(db, project_id, m.user, "source.uploaded", "source", src.id, filename=name,
              access_label=access_label, status=src.status, units=src.unit_count)
        db.commit()
        results.append({"filename": name, "ok": src.status == "parsed", "source": source_out(src),
                        "error": src.error})
    return {"results": results}


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
    try:
        full, parsed = fetch_repo(body.repo_url, body.token)
    except GitHubError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Could not reach GitHub: {e}") from e
    src = Source(project_id=project_id, kind="github", filename=f"GitHub · {full}",
                 uri=f"https://github.com/{full}", access_label=level, authorised_by=m.user.id)
    db.add(src)
    db.flush()
    store_units(db, src, parsed)
    # The token is used once and never stored.
    audit(db, project_id, m.user, "source.github_imported", "source", src.id, repo=full, units=src.unit_count,
          access_label=body.access_label)
    db.commit()
    return source_out(src)
