"""Baton API. Run locally with:  uvicorn app.main:app --reload  (from the backend folder)."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .ask.router import router as ask_router
from .audit.router import router as audit_router
from .auth.router import router as auth_router
from .config import get_settings
from .db import init_db
from .detect.router import router as detect_router
from .handover.router import router as handover_router
from .ingest.router import router as evidence_router
from .llm.provider import ai_status
from .projects.router import router as projects_router
from .share.router import router as share_router
from .sources.router import router as sources_router
from .team.router import router as team_router
from .verify.router import router as claims_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("baton")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    settings.check()  # refuses to start in production with the development secret
    init_db()
    if settings.run_worker:
        from .jobs import recover_interrupted, start_workers

        recover_interrupted()
        start_workers()
    if settings.app_secret.startswith("dev-only"):
        log.warning("APP_SECRET is the development default. Set a long random APP_SECRET in production.")
    log.info("Baton API ready. AI: %s. Email: %s.", ai_status(), "configured" if settings.email_configured else "not configured")
    yield
    from .jobs import stop_workers

    stop_workers()


app = FastAPI(
    lifespan=lifespan,
    title="Baton API",
    version="1.0.0",
    description="Evidence-first project handovers: Connect → Reconstruct → Verify → Review → Handover.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,  # exact addresses only (CORS_ORIGINS); no wildcards
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

for r in (
    auth_router,
    projects_router,
    sources_router,
    evidence_router,
    claims_router,
    detect_router,
    handover_router,
    share_router,
    audit_router,
    team_router,
    ask_router,
):
    app.include_router(r)


@app.get("/health", tags=["system"])
def health():
    """Liveness and readiness: database reachable, AI configured, job workers running."""
    from sqlalchemy import text

    from .db import engine
    from .jobs import status as jobs_status

    db_ok = True
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = False
    s = get_settings()
    body = {
        "ok": db_ok,
        "database": db_ok,
        "ai": ai_status(),
        "email": s.email_configured,
        "jobs": jobs_status() if db_ok else None,
    }
    return JSONResponse(body, status_code=200 if db_ok else 503)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on the server. Please try again."})
