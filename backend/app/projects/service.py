"""Project-level data operations shared by the API and maintenance tasks."""

from sqlalchemy.orm import Session

from ..models import (
    Acknowledgement,
    AuditEvent,
    Claim,
    ClaimEvidence,
    Conflict,
    EmailLog,
    EvidenceUnit,
    Gap,
    HandoverVersion,
    Invite,
    Job,
    Membership,
    Project,
    Question,
    Review,
    Source,
)


def delete_project(db: Session, project_id: str) -> None:
    """Delete a project and everything in it, children first so it works with or without database-level
    cascades (SQLite doesn't enforce them by default). Nothing from the project is kept anywhere: Baton
    doesn't store original files, only the redacted evidence text, which is deleted here."""
    claim_ids = [c for (c,) in db.query(Claim.id).filter_by(project_id=project_id)]
    version_ids = [v for (v,) in db.query(HandoverVersion.id).filter_by(project_id=project_id)]
    if claim_ids:
        db.query(ClaimEvidence).filter(ClaimEvidence.claim_id.in_(claim_ids)).delete(synchronize_session=False)
        db.query(Review).filter(Review.claim_id.in_(claim_ids)).delete(synchronize_session=False)
    if version_ids:
        db.query(Acknowledgement).filter(Acknowledgement.version_id.in_(version_ids)).delete(synchronize_session=False)
    for model in (
        Question,
        Gap,
        Conflict,
        Claim,
        HandoverVersion,
        EvidenceUnit,
        Source,
        Invite,
        Job,
        AuditEvent,
        EmailLog,
        Membership,
    ):
        db.query(model).filter_by(project_id=project_id).delete(synchronize_session=False)
    db.query(Project).filter_by(id=project_id).delete(synchronize_session=False)
