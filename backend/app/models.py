"""Database tables. Mirrors backend/sql/schema.sql (which adds Supabase Row-Level Security policies)."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex[:12]


# Access labels: who may see content from a source. A member sees labels <= their access level.
TEAM, LEADS, RESTRICTED = 1, 2, 3
LABELS = {TEAM: "Team", LEADS: "Leads", RESTRICTED: "Restricted"}
LABEL_BY_NAME = {v.lower(): k for k, v in LABELS.items()}

ROLES = ("admin", "reviewer", "departing", "incoming", "viewer")

CLAIM_TYPES = (
    "decision", "task", "owner", "blocker", "dependency",
    "risk", "open_question", "recurring_problem", "contact",
)
APPROVED_STATES = ("approved", "corrected")  # what may enter the handover

CONFIDENCE = (
    "verified", "corroborated", "weak", "conflicting",
    "unverified", "leaver_attested", "reviewer_asserted",
)


class Account(Base):
    """A browser session's owner (guest or signed-in). Personas it creates belong to it."""
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(16), default="guest")  # guest | supabase
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class User(Base):
    """A person. Either a signed-up account holder (has email + password) or a person a reviewer has named
    but who hasn't joined yet (no email). When that person accepts an invite, their memberships move to their
    own account and this record is marked merged_into."""
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    handle: Mapped[str | None] = mapped_column(String(120), nullable=True)  # e.g. GitHub username
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    merged_into: Mapped[str | None] = mapped_column(String(24), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Invite(Base):
    """A one-time link that lets a named person join a project with their own account."""
    __tablename__ = "invites"
    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))  # the named person this invite is for
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(16))
    access_level: Mapped[int] = mapped_column(Integer, default=TEAM)
    email_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(24), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_by: Mapped[str | None] = mapped_column(String(24), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    departing_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    incoming_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("project_id", "user_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    access_level: Mapped[int] = mapped_column(Integer, default=TEAM)
    user: Mapped[User] = relationship()


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # pdf docx txt md csv json chat github attestation
    filename: Mapped[str] = mapped_column(String(255))
    uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    access_label: Mapped[int] = mapped_column(Integer, default=TEAM)
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued parsed unreadable failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit_count: Mapped[int] = mapped_column(Integer, default=0)
    redactions: Mapped[int] = mapped_column(Integer, default=0)
    coverage: Mapped[dict] = mapped_column(JSON, default=dict)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    authorised_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class EvidenceUnit(Base):
    __tablename__ = "evidence_units"
    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(16))  # human-readable, e.g. E-12 (unique per project)
    seq: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(32))
    text: Mapped[str] = mapped_column(Text)
    text_hash: Mapped[str] = mapped_column(String(64))
    author: Mapped[str | None] = mapped_column(String(160), nullable=True)
    occurred_at: Mapped[str | None] = mapped_column(String(40), nullable=True)  # ISO date or "YYYY-MM-DD HH:MM"
    location: Mapped[dict] = mapped_column(JSON, default=dict)
    access_label: Mapped[int] = mapped_column(Integer, default=TEAM)
    analysed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[Source] = relationship()


class Claim(Base):
    __tablename__ = "claims"
    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(16))  # C-1, C-2 ...
    type: Mapped[str] = mapped_column(String(24))
    subject: Mapped[str] = mapped_column(String(200), default="")
    statement: Mapped[str] = mapped_column(Text)
    original_statement: Mapped[str] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(24), nullable=True)  # task status
    owner: Mapped[str | None] = mapped_column(String(160), nullable=True)
    owner_reassigned: Mapped[bool] = mapped_column(Boolean, default=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str] = mapped_column(String(24), default="unverified")
    support: Mapped[str | None] = mapped_column(String(16), nullable=True)  # gate 2 verdict
    support_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_state: Mapped[str] = mapped_column(String(16), default="pending")  # pending approved corrected rejected superseded
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    leaver_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    leaver_evidence_id: Mapped[str | None] = mapped_column(String(24), nullable=True)
    access_label: Mapped[int] = mapped_column(Integer, default=TEAM)
    extractor: Mapped[str] = mapped_column(String(80), default="")
    # Living handover: set when evidence that arrived after approval disagrees with or replaces this claim.
    changed_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(24), nullable=True)  # the analysis run that found it
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    citations: Mapped[list["ClaimEvidence"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan", order_by="ClaimEvidence.id"
    )


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    evidence_id: Mapped[str | None] = mapped_column(ForeignKey("evidence_units.id"), nullable=True)
    cited_code: Mapped[str] = mapped_column(String(16))  # what the AI cited, kept even if invalid
    quote: Mapped[str] = mapped_column(Text)
    start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    match: Mapped[str] = mapped_column(String(16), default="none")  # exact fuzzy none missing_evidence
    match_score: Mapped[float] = mapped_column(Float, default=0.0)
    claim: Mapped[Claim] = relationship(back_populates="citations")
    evidence: Mapped[EvidenceUnit | None] = relationship()


class Gap(Base):
    __tablename__ = "gaps"
    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    claim_id: Mapped[str | None] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), nullable=True)
    conflict_id: Mapped[str | None] = mapped_column(String(24), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(24), nullable=True)
    kind: Mapped[str] = mapped_column(String(32))  # missing_owner missing_reason open_question conflict unreadable_source
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open answered dismissed
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_evidence_id: Mapped[str | None] = mapped_column(String(24), nullable=True)
    access_label: Mapped[int] = mapped_column(Integer, default=TEAM)


class Conflict(Base):
    __tablename__ = "conflicts"
    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(24))  # status owner superseded
    claim_a_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"))
    claim_b_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"))
    explanation: Mapped[str] = mapped_column(Text)
    # Every claim on each side of the disagreement (claim_a/claim_b are one representative each).
    side_a: Mapped[list] = mapped_column(JSON, default=list)
    side_b: Mapped[list] = mapped_column(JSON, default=list)
    newer_side: Mapped[str | None] = mapped_column(String(1), nullable=True)  # "a" | "b" | None
    status: Mapped[str] = mapped_column(String(16), default="open")  # open resolved kept
    winner_claim_id: Mapped[str | None] = mapped_column(String(24), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_label: Mapped[int] = mapped_column(Integer, default=TEAM)


class HandoverVersion(Base):
    __tablename__ = "handover_versions"
    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft approved superseded
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    diff: Mapped[dict] = mapped_column(JSON, default=dict)  # what changed since the previous approved version
    created_by: Mapped[str | None] = mapped_column(String(24), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(24), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Acknowledgement(Base):
    __tablename__ = "acknowledgements"
    __table_args__ = (UniqueConstraint("version_id", "user_id", "section"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("handover_versions.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(String(24))
    section: Mapped[str] = mapped_column(String(40))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    reviewer_id: Mapped[str] = mapped_column(String(24))
    action: Mapped[str] = mapped_column(String(16))
    before: Mapped[dict] = mapped_column(JSON, default=dict)
    after: Mapped[dict] = mapped_column(JSON, default=dict)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditEvent(Base):
    """Append-only. The API never updates or deletes rows here."""
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[str | None] = mapped_column(String(24), nullable=True)
    actor_name: Mapped[str] = mapped_column(String(120), default="system")
    action: Mapped[str] = mapped_column(String(60))
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(24), nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Question(Base):
    """Ask Baton: a member's question, answered only from evidence they may see, with checked quotes."""
    __tablename__ = "questions"
    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    asked_by: Mapped[str] = mapped_column(String(24), index=True)
    asked_by_name: Mapped[str] = mapped_column(String(120), default="")
    access_level: Mapped[int] = mapped_column(Integer, default=TEAM)  # asker's level when asked
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="answered")  # answered unanswered sent answered_by_person
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    rejected_quotes: Mapped[int] = mapped_column(Integer, default=0)
    gap_id: Mapped[str | None] = mapped_column(String(24), nullable=True)
    person_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    person_answer_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(24), default="analyse")
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued running done failed
    stage: Mapped[str] = mapped_column(String(40), default="")
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LLMCache(Base):
    __tablename__ = "llm_cache"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    task: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(80))
    response: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
