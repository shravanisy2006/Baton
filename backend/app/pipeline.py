"""The analysis run: Reconstruct -> Verify -> Detect, as one background job.

Two modes:
- full ("analyse"): the first analysis, or "Start over". Every evidence unit is read again.
- update: only evidence that arrived since the last run (new uploads, a GitHub re-sync) is read. Existing claims
  and every review decision stay as they are. New claims that restate an existing one become extra support for
  it; new claims that disagree with or replace an approved one raise a conflict and mark that approved line
  "Changed since approval", so the reviewer can decide and issue a new handover version.
"""
import logging
from datetime import datetime, timezone

from .audit.service import log as audit
from .db import SessionLocal
from .detect.service import dedupe, detect_conflicts, detect_gaps, detect_supersessions
from .extract.service import extract_batch, make_batches
from .llm.provider import AIUnavailable, InvalidAIOutput
from .models import APPROVED_STATES, Claim, Conflict, EvidenceUnit, Gap, HandoverVersion, Job, Source, User
from .verify.service import base_confidence, gate1, gate2, refresh_confidence, valid_citations

log = logging.getLogger("baton.pipeline")


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


def run_analysis(project_id: str, job_id: str, actor_id: str | None = None) -> None:
    db = SessionLocal()
    job = db.get(Job, job_id)
    actor = db.get(User, actor_id) if actor_id else None
    update = job.kind == "update"
    try:
        job.status = "running"
        _stage(db, job, "preparing")
        if not update:
            reset_analysis(db, project_id)
        q = (db.query(EvidenceUnit).filter_by(project_id=project_id)
             .filter(EvidenceUnit.kind != "attestation"))
        if update:
            q = q.filter(EvidenceUnit.analysed_at.is_(None))
        units = q.order_by(EvidenceUnit.seq).all()
        if not units:
            raise RuntimeError("No new evidence since the last analysis. Upload files or re-sync GitHub first."
                               if update else "No evidence yet. Upload at least one readable source first.")
        existing: list[Claim] = []
        if update:
            existing = (db.query(Claim).filter_by(project_id=project_id)
                        .filter(Claim.review_state.notin_(("rejected", "superseded"))).all())
        filenames = {s.id: s.filename for s in db.query(Source).filter_by(project_id=project_id)}
        warnings: list[str] = []

        _stage(db, job, "extracting claims")
        claims: list[Claim] = []
        batches = make_batches(units, filenames)
        analysed: list[EvidenceUnit] = []
        for n, batch in enumerate(batches, start=1):
            try:
                claims += extract_batch(db, project_id, batch, filenames)
                analysed += batch
            except InvalidAIOutput as e:
                warnings.append(f"Batch {n} of {len(batches)} ({batch[0].code}–{batch[-1].code}) was not analysed: "
                                f"the AI returned invalid output twice. ({e})")
            except AIUnavailable as e:
                if not claims and n == 1:
                    raise
                warnings.append(f"Batch {n} of {len(batches)} ({batch[0].code}–{batch[-1].code}) was not analysed: {e}")
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
                        what = "may be replaced by newer evidence" if k.kind == "superseded" else "is contradicted by newer evidence"
                        c.changed_note = f"This approved line {what}: {k.explanation[:400]}"
                        c.changed_at = now
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
        audit(db, project_id, actor, "analysis.updated" if update else "analysis.completed", "job", job.id,
              **job.stats)
        db.commit()
    except Exception as e:  # noqa: BLE001
        db.rollback()
        job = db.get(Job, job_id)
        job.status = "failed"
        job.error = str(e)[:1000]
        job.finished_at = datetime.now(timezone.utc)
        audit(db, project_id, actor, "analysis.failed", "job", job.id, error=str(e)[:300])
        db.commit()
        log.exception("Analysis failed for %s", project_id)
    finally:
        db.close()
