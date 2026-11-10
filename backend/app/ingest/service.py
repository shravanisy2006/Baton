"""Store parsed units as evidence: redact, hash, number (E-1, E-2 ...) and inherit the source's access label."""
import hashlib

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import EvidenceUnit, Source
from .parsers import ParsedSource
from .redact import redact


def _hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.lower().split()).encode()).hexdigest()


def next_seq(db: Session, project_id: str) -> int:
    current = db.query(func.max(EvidenceUnit.seq)).filter_by(project_id=project_id).scalar()
    return (current or 0) + 1


def store_units(db: Session, source: Source, parsed: ParsedSource) -> int:
    seq = next_seq(db, source.project_id)
    redactions = 0
    for unit in parsed.units:
        text, n = redact(unit.text)
        redactions += n
        db.add(EvidenceUnit(
            project_id=source.project_id, source_id=source.id, code=f"E-{seq}", seq=seq,
            kind=unit.kind, text=text, text_hash=_hash(text),
            author=unit.author or parsed.author, occurred_at=unit.occurred_at or parsed.occurred_at,
            location=unit.location, access_label=source.access_label,
        ))
        seq += 1
    source.unit_count = len(parsed.units)
    source.redactions = redactions
    source.coverage = {"units": len(parsed.units), "skipped": parsed.skipped[:50], "skipped_count": len(parsed.skipped)}
    if parsed.unreadable or not parsed.units:
        source.status = "unreadable"
        source.error = "No readable text found." if not parsed.skipped else "; ".join(parsed.skipped[:3])
    else:
        source.status = "parsed"
        source.error = None
    return len(parsed.units)
