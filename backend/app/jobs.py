"""Background jobs: a persistent queue in the database, worked by a small pool of worker threads.

Why this design: on Render's free plan there is one process and no separate worker service, so the queue lives in
the `jobs` table and worker threads run inside the API process. Because the queue is in the database:
- a request never runs the analysis itself; it only adds a queued job and returns at once;
- a restart (deploy, crash, the free server sleeping) doesn't lose work: jobs that were running are put back in
  the queue and resumed (up to MAX_ATTEMPTS), and the pipeline first removes partial results of the interrupted
  attempt, so nothing is duplicated;
- moving the workers to their own process later needs no code change: set BATON_RUN_WORKER=0 on the API and run
  `python -m app.worker` as a separate service.

Jobs for the same project never run at the same time (the API refuses to queue a second one).
"""

import logging
import os
import threading
import time
from datetime import datetime, timezone

from .config import get_settings
from .db import SessionLocal
from .models import Job

log = logging.getLogger("baton.jobs")
MAX_ATTEMPTS = 3
POLL_SECONDS = 5
MAINTENANCE_SECONDS = 3600

_wake = threading.Event()
_stop = threading.Event()
_threads: list[threading.Thread] = []
_last_maintenance = 0.0


def inline() -> bool:
    """Tests run jobs inside the request so results are ready when the request returns (same code path)."""
    return os.environ.get("BATON_JOBS_INLINE") == "1"


def enqueue(db, project_id: str, kind: str, actor_id: str | None) -> Job:
    job = Job(project_id=project_id, kind=kind, actor_id=actor_id, status="queued", stage="waiting to start")
    db.add(job)
    db.flush()
    return job


def after_commit(job_id: str) -> None:
    """Call once the request has committed the queued job."""
    if inline():
        run_job_now(job_id)
    else:
        kick()


def kick() -> None:
    _wake.set()


def _claim(job_id: str | None = None) -> str | None:
    with SessionLocal() as db:
        q = db.query(Job).filter(Job.status == "queued")
        if job_id:
            q = q.filter(Job.id == job_id)
        job = q.order_by(Job.created_at).first()
        if not job:
            return None
        claimed = (
            db.query(Job)
            .filter(Job.id == job.id, Job.status == "queued")
            .update(
                {"status": "running", "started_at": datetime.now(timezone.utc), "attempts": (job.attempts or 0) + 1},
                synchronize_session=False,
            )
        )
        db.commit()
        return job.id if claimed == 1 else None


def _execute(job_id: str) -> None:
    from .pipeline import run_analysis

    with SessionLocal() as db:
        job = db.get(Job, job_id)
        project_id, actor_id = job.project_id, job.actor_id
    run_analysis(project_id, job_id, actor_id)


def run_job_now(job_id: str) -> None:
    """Run one queued job in the calling thread (tests, and building a demo sandbox)."""
    if _claim(job_id):
        _execute(job_id)


def recover_interrupted() -> int:
    """At start-up: jobs left 'running' were cut off by a restart. Queue them again, or fail them for good after
    MAX_ATTEMPTS so a job that crashes the server can't loop forever."""
    with SessionLocal() as db:
        stuck = db.query(Job).filter(Job.status == "running").all()
        for j in stuck:
            if (j.attempts or 0) >= MAX_ATTEMPTS:
                j.status, j.finished_at = "failed", datetime.now(timezone.utc)
                j.error = "The server restarted several times while this analysis was running. Press Re-run analysis."
            else:
                j.status, j.stage = "queued", "resuming after a server restart"
        db.commit()
        if stuck:
            log.warning("Re-queued or failed %d interrupted job(s).", len(stuck))
        return len(stuck)


def _maintenance() -> None:
    global _last_maintenance
    if time.time() - _last_maintenance < MAINTENANCE_SECONDS:
        return
    _last_maintenance = time.time()
    try:
        from .sandbox import cleanup_old_sandboxes

        cleanup_old_sandboxes()
    except Exception:  # noqa: BLE001
        log.exception("Maintenance failed")


def _loop(n: int) -> None:
    log.info("Job worker %d started", n)
    while not _stop.is_set():
        try:
            if n == 0:
                _maintenance()
            job_id = _claim()
            if job_id:
                _execute(job_id)
                continue
        except Exception:  # noqa: BLE001 — a worker must never die
            log.exception("Job worker %d error", n)
        _wake.wait(POLL_SECONDS)
        _wake.clear()
    log.info("Job worker %d stopped", n)


def start_workers() -> None:
    if _threads:
        return
    _stop.clear()
    for n in range(max(1, get_settings().worker_threads)):
        t = threading.Thread(target=_loop, args=(n,), name=f"baton-worker-{n}", daemon=True)
        t.start()
        _threads.append(t)


def stop_workers(timeout: float = 5) -> None:
    _stop.set()
    _wake.set()
    for t in _threads:
        t.join(timeout)
    _threads.clear()


def status() -> dict:
    with SessionLocal() as db:
        queued = db.query(Job).filter(Job.status == "queued").count()
        running = db.query(Job).filter(Job.status == "running").count()
    return {"workers": sum(t.is_alive() for t in _threads), "queued": queued, "running": running}
