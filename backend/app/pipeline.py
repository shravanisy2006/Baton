"""The analysis run: Reconstruct -> Verify -> Detect, as one background job.

Two modes:
- full ("analyse"): the first analysis, or "Start over". Every evidence unit is read again.
- update: only evidence that arrived since the last run (new uploads, a GitHub re-sync) is read. Existing claims
  and every review decision stay as they are. New claims that restate an existing one become extra support for
  it; new claims that disagree with or replace an approved one raise a conflict and mark that approved line
  "Changed since approval", so the reviewer can decide and issue a new handover version.
"""

import logging
import os
import time
from datetime import datetime, timezone

from .audit.service import log as audit
from .db import SessionLocal
from .detect.service import assign_topics, dedupe, detect_conflicts, detect_gaps, detect_supersessions
from .extract.service import make_batches
from .llm.provider import AIUnavailable, InvalidAIOutput
from .models import APPROVED_STATES, Claim, Conflict, EvidenceUnit, Gap, HandoverVersion, Job, Source, User
from .verify.service import base_confidence, gate1, gate2, refresh_confidence, valid_citations

log = logging.getLogger("baton.pipeline")
BUSY_WAIT_SECONDS = float(os.environ.get("BATON_BUSY_WAIT_SECONDS", "20"))


def _stage(db, job: Job, stage: str) -> None:
    job.stage = stage
    db.commit()


def reset_analysis(db, project_id: str) -> None:
    """Start over: drop claims, gaps and conflicts. An approved handover stays readable until a new one is
    approved (its snapshot is self-contained); unapproved drafts are discarded."""
    db.query(Gap).filter_by(project_id=project_id).delete()
    db.query(Conflict).filter_by(project_id=project_id).delete()
    for c in db.query(Claim).filter_by(project_id=project_id).all():
        db.delete(c)
    db.query(HandoverVersion).filter_by(project_id=project_id, status="draft").update({"status": "superseded"})
    db.query(EvidenceUnit).filter_by(project_id=project_id).update({"analysed_at": None})
    db.flush()


def _remove_partial_results(db, job_id: str) -> None:
    """A resumed job (after a restart) first removes what its interrupted attempt had already saved."""
    leftovers = db.query(Claim).filter_by(job_id=job_id).all()
    if not leftovers:
        return
    ids = [c.id for c in leftovers]
    db.query(Gap).filter(Gap.claim_id.in_(ids)).delete(synchronize_session=False)
    db.query(Conflict).filter(Conflict.claim_a_id.in_(ids) | Conflict.claim_b_id.in_(ids)).delete(synchronize_session=False)
    for c in leftovers:
        db.delete(c)
    db.flush()


def _extract_all(db, job: Job, project_id: str, batches, filenames, warnings: list[str]):
    """Ask the AI about every batch, several batches at a time (AI_CONCURRENCY), then save the claims in batch
    order so claim numbers are stable. A busy AI gets one wait-and-retry per batch."""
    from concurrent.futures import ThreadPoolExecutor

    from .config import get_settings
    from .extract.service import ask_extract, save_claims

    def work(batch):
        with SessionLocal() as tdb:  # each thread uses its own session for the AI response cache
            try:
                return ask_extract(tdb, batch, filenames), None
            except AIUnavailable:
                time.sleep(BUSY_WAIT_SECONDS)
                try:
                    return ask_extract(tdb, batch, filenames), None
                except (AIUnavailable, InvalidAIOutput) as e:
                    return None, e
            except InvalidAIOutput as e:
                return None, e

    workers = max(1, min(get_settings().ai_concurrency, len(batches)))
    _stage(db, job, f"extracting claims ({len(batches)} part{'s' if len(batches) != 1 else ''})")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(work, batches))
    claims, analysed, errors = [], [], []
    for n, (batch, (res, err)) in enumerate(zip(batches, results, strict=False), start=1):
        if res is not None:
            claims += save_claims(db, project_id, res)
            analysed += batch
            continue
        errors.append(err)
        if isinstance(err, InvalidAIOutput):
            warnings.append(
                f"Part {n} of {len(batches)} ({batch[0].code}–{batch[-1].code}) was not analysed: "
                f"the AI returned invalid output twice. ({err})"
            )
        else:
            warnings.append(
                f"Part {n} of {len(batches)} ({batch[0].code}–{batch[-1].code}) was not analysed because "
                f"the AI was busy; those pieces stay waiting, so 'Analyse new evidence' finishes them "
                f"later without redoing the rest. ({str(err)[:120]})"
            )
    if not analysed and errors and all(isinstance(e, AIUnavailable) for e in errors):
        raise errors[0]
    return claims, analysed


def run_analysis(project_id: str, job_id: str, actor_id: str | None = None) -> None:
    db = SessionLocal()
    job = db.get(Job, job_id)
    actor = db.get(User, actor_id) if actor_id else None
    update = job.kind == "update"
    try:
        job.status = "running"
        _stage(db, job, "preparing")
        _remove_partial_results(db, job_id)
        if not update:
            reset_analysis(db, project_id)
        q = db.query(EvidenceUnit).filter_by(project_id=project_id).filter(EvidenceUnit.kind != "attestation")
        if update:
            q = q.filter(EvidenceUnit.analysed_at.is_(None))
        units = q.order_by(EvidenceUnit.seq).all()
        if not units:
            raise RuntimeError(
                "No new evidence since the last analysis. Upload files or re-sync GitHub first."
                if update
                else "No evidence yet. Upload at least one readable source first."
            )
        existing: list[Claim] = []
        if update:
            existing = (
                db.query(Claim)
                .filter_by(project_id=project_id)
                .filter(Claim.review_state.notin_(("rejected", "superseded")))
                .all()
            )
        filenames = {s.id: s.filename for s in db.query(Source).filter_by(project_id=project_id)}
        warnings: list[str] = []

        batches = make_batches(units, filenames)
        claims, analysed = _extract_all(db, job, project_id, batches, filenames, warnings)
        for c in claims:
            c.job_id = job.id
        db.commit()

        _stage(db, job, "checking quotes")
        gate1(db, project_id, claims)
        db.flush()
        before = len(claims)
        claims = dedupe(db, claims, existing)
        merged_into_existing = before - len(claims) if update else 0
        db.commit()

        _stage(db, job, "checking support")
        try:
            warnings += gate2(db, claims)
        except (AIUnavailable, InvalidAIOutput) as e:
            warnings.append(f"Support check unavailable, affected claims stay Unverified: {e}")
        for c in claims:
            c.confidence = base_confidence(c)
        db.commit()

        _stage(db, job, "finding gaps and conflicts")
        new_ids = {c.id for c in claims} if update else None
        pool = existing + claims
        warnings += assign_topics(db, [c for c in pool if valid_citations(c)])
        conflicts = detect_conflicts(db, project_id, pool, new_ids)
        _stage(db, job, "checking the timeline")
        superseded, w = detect_supersessions(db, project_id, pool, new_ids)
        conflicts += superseded
        warnings += w
        gaps = detect_gaps(db, project_id, claims, conflicts)

        # Living handover: approved lines that new evidence disagrees with or replaces.
        affected: list[Claim] = []
        if update:
            by_id = {c.id: c for c in pool}
            now = datetime.now(timezone.utc)
            for k in conflicts:
                for cid in k.side_a + k.side_b:
                    c = by_id.get(cid)
                    if c and c.id not in new_ids and c.review_state in APPROVED_STATES and c not in affected:
                        what = (
                            "may be replaced by newer evidence" if k.kind == "superseded" else "is contradicted by newer evidence"
                        )
                        c.changed_note = f"This approved line {what}: {k.explanation[:400]}"
                        c.changed_at = now
                        newer = [by_id[x] for x in k.side_a + k.side_b if x in new_ids and x in by_id]
                        c.changed_evidence = [
                            {
                                "code": x.evidence.code,
                                "quote": x.quote,
                                "source": filenames.get(x.evidence.source_id, ""),
                                "author": x.evidence.author,
                                "date": x.evidence.occurred_at,
                                "text": x.evidence.text,
                                "start": x.start,
                                "end": x.end,
                                "access_level": x.evidence.access_label,
                                "statement": n.statement,
                            }
                            for n in newer
                            for x in n.citations
                            if x.match == "exact" and x.evidence
                        ][:4]
                        affected.append(c)
        for c in claims + affected:
            refresh_confidence(db, c)
        stamp = datetime.now(timezone.utc)
        for u in analysed:
            u.analysed_at = stamp

        rejected_quotes = sum(1 for c in claims for x in c.citations if x.match not in ("exact", "fuzzy"))
        job.stats = {
            "mode": "update" if update else "full",
            "evidence_units": len(units),
            "claims": len(claims),
            "verified": sum(c.confidence in ("verified", "corroborated") for c in claims),
            "weak": sum(c.confidence == "weak" for c in claims),
            "unverified": sum(c.confidence == "unverified" for c in claims),
            "failed_gate1": sum(1 for c in claims if not valid_citations(c)),
            "rejected_quotes": rejected_quotes,
            "conflicts": len(conflicts),
            "superseded": len(superseded),
            "near_miss_quotes": sum(1 for c in claims for x in c.citations if x.match == "fuzzy"),
            "gaps": len(gaps),
            "merged_into_existing": merged_into_existing,
            "changed_since_approval": len(affected),
        }
        job.warnings = warnings
        job.status = "done"
        job.stage = "finished"
        job.finished_at = datetime.now(timezone.utc)
        audit(db, project_id, actor, "analysis.updated" if update else "analysis.completed", "job", job.id, **job.stats)
        db.commit()
    except Exception as e:  # noqa: BLE001
        db.rollback()
        job = db.get(Job, job_id)
        job.status = "failed"
        job.error = (
            (
                "The AI (Gemini) is busy or over its free limit right now, even after retrying. Nothing was "
                "lost: wait a minute and run the analysis again. Details: "
            )
            if isinstance(e, AIUnavailable)
            else ""
        ) + str(e)[:900]
        job.finished_at = datetime.now(timezone.utc)
        audit(db, project_id, actor, "analysis.failed", "job", job.id, error=str(e)[:300])
        db.commit()
        log.exception("Analysis failed for %s", project_id)
    finally:
        db.close()
