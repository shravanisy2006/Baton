"""Baton API. Run locally with:  uvicorn app.main:app --reload  (from the backend folder)."""

import logging
import os
import re
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
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
# The deployed commit (Render sets RENDER_GIT_COMMIT), shown by /health so anyone can check what is live.
VERSION = (os.environ.get("RENDER_GIT_COMMIT") or os.environ.get("BATON_VERSION") or "dev")[:7]
_SECRETISH = re.compile(r"/[A-Za-z0-9_-]{20,}")  # invite / reset / confirmation tokens in URLs
SLOW_REQUEST_SECONDS = 5.0


def safe_path(path: str) -> str:
    """The request path with one-time tokens masked, so logs never contain a usable link."""
    return _SECRETISH.sub("/[token]", path)


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
app.add_middleware(GZipMiddleware, minimum_size=1000)
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


@app.middleware("http")
async def request_context(request: Request, call_next):
    """A short reference for every request (returned as X-Request-ID and shown in server-error messages), basic
    security headers, and a log line for errors and slow requests. Tokens in paths are masked in logs."""
    ref = uuid.uuid4().hex[:8]
    request.state.ref = ref
    start = time.perf_counter()
    response = await call_next(request)
    took = time.perf_counter() - start
    response.headers["X-Request-ID"] = ref
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers.setdefault("Cache-Control", "no-store")  # responses are personal: never cache them
    if response.status_code >= 500 or took > SLOW_REQUEST_SECONDS:
        log.warning("ref=%s %s %s -> %s in %.1fs", ref, request.method, safe_path(request.url.path), response.status_code, took)
    return response


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
        "version": VERSION,
        "database": db_ok,
        "ai": ai_status(),
        "email": s.email_configured,
        "jobs": jobs_status() if db_ok else None,
    }
    return JSONResponse(body, status_code=200 if db_ok else 503)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    ref = getattr(request.state, "ref", uuid.uuid4().hex[:8])
    log.exception("ref=%s unhandled error on %s %s", ref, request.method, safe_path(request.url.path))
    return JSONResponse(
        status_code=500,
        content={"detail": f"Something went wrong on the server. Please try again. (Reference: {ref})", "reference": ref},
        headers={"X-Request-ID": ref},
    )
