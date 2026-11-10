from sqlalchemy.orm import Session

from ..models import AuditEvent, User


def log(db: Session, project_id: str, actor: User | None, action: str,
        target_type: str | None = None, target_id: str | None = None, **detail) -> None:
    """Append one audit event. Callers commit with their own transaction."""
    db.add(AuditEvent(
        project_id=project_id,
        actor_id=actor.id if actor else None,
        actor_name=actor.name if actor else "Baton",
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
    ))
