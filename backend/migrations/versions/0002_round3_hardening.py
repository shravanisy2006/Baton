"""Accounts security, persistent job queue, email, evidence flags and topics.

Revision ID: 0002
Revises: 0001

Written to be safe on any database Baton has created: every step checks what already exists, so it also works
on a database created from sql/schema.sql or by an older start-up routine.
"""

import logging

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None
log = logging.getLogger("alembic.baton")


def _cols(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> dict[str, bool]:
    return {i["name"]: bool(i["unique"]) for i in sa.inspect(op.get_bind()).get_indexes(table)}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _tables()
    if "tokens" not in tables:
        op.create_table(
            "tokens",
            sa.Column("id", sa.String(24), primary_key=True),
            sa.Column("user_id", sa.String(24), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("kind", sa.String(16), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_tokens_token_hash", "tokens", ["token_hash"], unique=True)
        op.create_index("ix_tokens_user_id", "tokens", ["user_id"])
    if "email_log" not in tables:
        op.create_table(
            "email_log",
            sa.Column("id", sa.String(24), primary_key=True),
            sa.Column("project_id", sa.String(24), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
            sa.Column("kind", sa.String(32), nullable=False),
            sa.Column("to_hint", sa.String(80), nullable=False),
            sa.Column("subject", sa.String(200), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_email_log_project_id", "email_log", ["project_id"])

    adds = {
        "claims": [sa.Column("topic", sa.String(200), nullable=True)],
        "evidence_units": [sa.Column("flags", sa.JSON(), nullable=False, server_default=sa.text("'[]'"))],
        "jobs": [
            sa.Column("actor_id", sa.String(24), nullable=True),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        ],
        "users": [
            sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        ],
    }
    for table, columns in adds.items():
        have = _cols(table)
        missing = [c for c in columns if c.name not in have]
        if missing:
            with op.batch_alter_table(table) as b:
                for c in missing:
                    b.add_column(c)

    if "ix_jobs_status" not in _indexes("jobs"):
        op.create_index("ix_jobs_status", "jobs", ["status"])

    # Email must be unique. Earlier versions checked this only in code; if two accounts ever shared an address,
    # keep the oldest and detach the address from the others (logged), so the unique index can be created.
    bind = op.get_bind()
    dupes = bind.execute(
        sa.text("SELECT lower(email) FROM users WHERE email IS NOT NULL GROUP BY lower(email) HAVING count(*) > 1")
    ).fetchall()
    for (email,) in dupes:
        ids = [
            r[0]
            for r in bind.execute(
                sa.text("SELECT id FROM users WHERE lower(email) = :e ORDER BY created_at"), {"e": email}
            ).fetchall()
        ]
        for extra in ids[1:]:
            bind.execute(sa.text("UPDATE users SET email = NULL WHERE id = :i"), {"i": extra})
            log.warning("Detached a duplicate email address from user %s", extra)
    # Supabase exposes tables in the public schema through its REST API unless Row-Level Security is on.
    # Baton connects as the table owner (which bypasses RLS), so enabling it with no policies blocks only
    # outside access, exactly as sql/schema.sql does for every other table.
    if bind.dialect.name == "postgresql":
        for t in ("tokens", "email_log", "alembic_version"):
            bind.execute(sa.text(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY"))
    idx = _indexes("users")
    if not idx.get("ix_users_email"):
        if "ix_users_email" in idx:
            op.drop_index("ix_users_email", table_name="users")
        op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.create_index("ix_users_email", "users", ["email"])
    op.drop_index("ix_jobs_status", table_name="jobs")
    for table, cols in {
        "users": ["deleted_at", "email_verified_at", "session_version"],
        "jobs": ["started_at", "attempts", "actor_id"],
        "evidence_units": ["flags"],
        "claims": ["topic"],
    }.items():
        with op.batch_alter_table(table) as b:
            for c in cols:
                b.drop_column(c)
    op.drop_table("email_log")
    op.drop_table("tokens")
