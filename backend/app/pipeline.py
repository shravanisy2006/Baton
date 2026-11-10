"""The analysis run: Reconstruct -> Verify -> Detect, as one background job."""
import logging
from datetime import datetime, timezone

from .audit.service import log as audit
from .db import SessionLocal
from .detect.service import dedupe, detect_conflicts, detect_gaps, detect_supersessions
from .extract.service import extract_batch, make_batches
from .llm.provider import AIUnavailable, InvalidAIOutput
from .models import Claim, Conflict, EvidenceUnit, Gap, HandoverVersion, Job, Source, User
from .verify.service import base_confidence, gate1, gate2, refresh_confidence, valid_citations

log = logging.getLogger("baton.pipeline")


def _stage(db, job: Job, stage: str) -> None:
    job.stage = stage
    db.commit()


def reset_analysis(db, project_id: str) -> None:
    db.query(Gap).filter_by(project_id=project_id).delete()
    db.query(Conflict).filter_by(project_id=project_id).delete()
    for c in db.query(Claim).filter_by(project_id=project_id).all():
        db.delete(c)
    db.query(HandoverVersion).filter_by(project_id=project_id).filter(
        HandoverVersion.status != "superseded").update({"status": "superseded"})
    db.flush()


def run_analysis(project_id: str, job_id: str, actor_id: str | None = None) -> None:
    db = SessionLocal()
    job = db.get(Job, job_id)
    actor = db.get(User, actor_id) if actor_id else None
    try:
        job.status = "running"
        _stage(db, job, "preparing")
        reset_analysis(db, project_id)
        units = (db.query(EvidenceUnit).filter_by(project_id=project_id)
                 .filter(EvidenceUnit.kind != "attestation").order_by(EvidenceUnit.seq).all())
        if not units:
            raise RuntimeError("No evidence yet. Upload at least one readable source first.")
        filenames = {s.id: s.filename for s in db.query(Source).filter_by(project_id=project_id)}
        warnings: list[str] = []

        _stage(db, job, "extracting claims")
        claims: list[Claim] = []
        batches = make_batches(units, filenames)
        for n, batch in enumerate(batches, start=1):
            try:
                claims += extract_batch(db, project_id, batch, filenames)
            except InvalidAIOutput as e:
                warnings.append(f"Batch {n} of {len(batches)} ({batch[0].code}–{batch[-1].code}) was not analysed: "
                                f"the AI returned invalid output twice. ({e})")
            except AIUnavailable as e:
                if not claims and n == 1:
                    raise
                warnings.append(f"Batch {n} of {len(batches)} ({batch[0].code}–{batch[-1].code}) was not analysed: {e}")
        db.commit()

        _stage(db, job, "checking quotes")
        gate1(db, project_id, claims)
        db.flush()
        claims = dedupe(db, claims)
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
        conflicts = detect_conflicts(db, project_id, claims)
        _stage(db, job, "checking the timeline")
        superseded, w = detect_supersessions(db, project_id, claims)
        conflicts += superseded
        warnings += w
        gaps = detect_gaps(db, project_id, claims, conflicts)
        for c in claims:
            refresh_confidence(db, c)

        rejected_quotes = sum(1 for c in claims for x in c.citations if x.match not in ("exact", "fuzzy"))
        job.stats = {
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
        }
        job.warnings = warnings
        job.status = "done"
        job.stage = "finished"
        job.finished_at = datetime.now(timezone.utc)
        audit(db, project_id, actor, "analysis.completed", "job", job.id, **job.stats)
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
