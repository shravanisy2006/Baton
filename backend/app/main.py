"""Baton API. Run locally with:  uvicorn app.main:app --reload  (from the backend folder)."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
from .verify.router import router as claims_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("baton")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    if get_settings().app_secret.startswith("dev-only"):
        log.warning("APP_SECRET is the development default. Set a long random APP_SECRET in production.")
    log.info("Baton API ready. AI: %s", ai_status())
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Baton API",
    version="1.0.0",
    description="Evidence-first project handovers: Connect → Reconstruct → Verify → Review → Handover.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth_router, projects_router, sources_router, evidence_router, claims_router, detect_router,
          handover_router, share_router, audit_router):
    app.include_router(r)


@app.get("/health", tags=["system"])
def health():
    return {"ok": True, "ai": ai_status()}


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on the server. Please try again."})
