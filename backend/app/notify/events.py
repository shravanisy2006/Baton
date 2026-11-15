"""Who gets an email when something important happens in a project. Each returns the delivery outcomes.

Only people who joined with their own (email) account are emailed, and never about content above their access
level: the emails say *that* something happened and link to Baton, which re-checks access when they open it.
"""

from sqlalchemy.orm import Session

from ..models import Membership, Project, User
from . import email as mail


def _members_with_email(
    db: Session, project_id: str, roles: tuple[str, ...] | None = None, exclude: str | None = None
) -> list[User]:
    q = db.query(Membership).filter_by(project_id=project_id)
    out = []
    for m in q.all():
        if roles and m.role not in roles:
            continue
        if m.user.email and not m.user.deleted_at and m.user.id != exclude:
            out.append(m.user)
    return out


def handover_approved(db: Session, project: Project, version: int, changes: int, approver_id: str | None) -> list[str]:
    what = f"Version {version} of the handover was approved" + (
        f", with {changes} change(s) since the last version." if version > 1 else "."
    )
    results = []
    for u in _members_with_email(db, project.id, ("incoming", "departing", "viewer", "admin", "reviewer"), approver_id):
        results.append(
            mail.send(
                db,
                u.email,
                f"{project.name}: handover version {version} is ready",
                f"Hi {u.name},\n\n{what}\n\nOpen it: {mail.link(f'/p/{project.id}/handover')}\n\n"
                + (
                    "Sections that didn't change keep your 'I've read this' marks; only changed sections need reading again."
                    if version > 1
                    else "Every line links to the evidence behind it."
                )
                + mail.FOOTER,
                "handover_approved",
                project.id,
            )
        )
    return results


def question_for_person(db: Session, project: Project, asked_by: str, gap_id: str) -> list[str]:
    targets = _members_with_email(db, project.id, ("departing",)) or _members_with_email(db, project.id, ("reviewer", "admin"))
    return [
        mail.send(
            db,
            u.email,
            f"{project.name}: {asked_by} has a question for you",
            f"Hi {u.name},\n\n{asked_by} asked Baton something the project's files don't answer, and it was "
            f"sent to you.\n\nAnswer it here: {mail.link(f'/p/{project.id}/gaps')}\n\nYour answer is saved as "
            f"labelled evidence and shown to them with your name." + mail.FOOTER,
            "question_sent",
            project.id,
        )
        for u in targets
    ]


def question_answered(db: Session, project: Project, asker_id: str, answered_by: str) -> list[str]:
    u = db.get(User, asker_id)
    if not u or not u.email or u.deleted_at:
        return []
    return [
        mail.send(
            db,
            u.email,
            f"{project.name}: your question was answered",
            f"Hi {u.name},\n\n{answered_by} answered the question you sent from Ask Baton.\n\n"
            f"See the answer: {mail.link(f'/p/{project.id}/ask')}" + mail.FOOTER,
            "question_answered",
            project.id,
        )
    ]


def invite(db: Session, project: Project, to: str, name: str, inviter: str, path: str) -> str:
    return mail.send(
        db,
        to,
        f"{inviter} invited you to the {project.name} handover on Baton",
        f"Hi {name},\n\n{inviter} added you to the handover for {project.name} on Baton.\n\nJoin here (the link "
        f"works once, for 14 days): {mail.link(path)}\n\nYou'll create your own account, or sign in, with "
        f"this email address." + mail.FOOTER,
        "invite",
        project.id,
    )
