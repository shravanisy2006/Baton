"""Create a fresh, private copy of the synthetic EventApp demo for one visitor.

All demo content is invented (see backend/seed/eventapp/README.md). Each visitor gets their own copy,
so judges can approve, reject and resolve things without affecting anyone else. The AI pipeline runs
for real; its responses are cached, so repeat demos cost no API quota.
"""
from sqlalchemy.orm import Session

from .audit.service import log as audit
from .config import BACKEND_DIR
from .ingest.parsers import parse_file
from .ingest.service import store_units
from .models import LEADS, RESTRICTED, TEAM, Account, Job, Membership, Project, Source, User

SEED_DIR = BACKEND_DIR / "seed" / "eventapp"

# (filename, access label) in a fixed order so evidence IDs, and therefore cache keys, stay stable.
SEED_FILES = [
    ("meeting-notes-2026-09-15.md", TEAM),
    ("tasks-export.csv", TEAM),
    ("github-export-eventapp.md", TEAM),
    ("deploy-runbook.pdf", TEAM),
    ("riya-handover-notes.docx", LEADS),
    ("sponsor-notes.md", RESTRICTED),
    ("club-whatsapp-export.txt", TEAM),
]

PEOPLE = [
    # name, handle, role, access level
    ("Priya Nair", "priya", "reviewer", RESTRICTED),
    ("Riya Sharma", "riya-dev", "departing", LEADS),
    ("Karan Mehta", "karan-m", "incoming", LEADS),
    ("Anika Joshi", "anika", "viewer", TEAM),
]


def create_demo(db: Session, account: Account) -> tuple[Project, User, Job]:
    users = {}
    for name, handle, role, level in PEOPLE:
        u = User(account_id=account.id, name=name, handle=handle)
        db.add(u)
        users[role] = (u, level)
    db.flush()
    project = Project(
        account_id=account.id, name="EventApp", is_demo=True,
        description="Synthetic demo: a college club's event registration app. Backend lead Riya is leaving; "
                    "Karan is taking over.",
        departing_user_id=users["departing"][0].id, incoming_user_id=users["incoming"][0].id,
    )
    db.add(project)
    db.flush()
    for role, (u, level) in users.items():
        db.add(Membership(project_id=project.id, user_id=u.id, role=role, access_level=level))
    reviewer = users["reviewer"][0]
    for filename, label in SEED_FILES:
        data = (SEED_DIR / filename).read_bytes()
        kind, parsed = parse_file(data, filename)
        src = Source(project_id=project.id, kind=kind,
                     filename=filename, access_label=label, authorised_by=reviewer.id,
                     storage_path=f"seed://eventapp/{filename}")
        db.add(src)
        db.flush()
        store_units(db, src, parsed)
    job = Job(project_id=project.id)
    db.add(job)
    db.flush()
    audit(db, project.id, reviewer, "demo.created", "project", project.id,
          note="Synthetic EventApp data loaded for this visitor only.")
    return project, reviewer, job
