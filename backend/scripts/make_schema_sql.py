"""Regenerate sql/schema.sql from the SQLAlchemy models (Postgres dialect), with Row-Level Security.
Run from the backend folder:  python scripts/make_schema_sql.py"""
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.dialects import postgresql  # noqa: E402
from sqlalchemy.schema import CreateIndex, CreateTable  # noqa: E402

from app.db import Base  # noqa: E402
import app.models  # noqa: E402,F401

HEAD = """-- Baton database schema for Supabase Postgres.
-- The API also creates these tables automatically on first start (SQLAlchemy create_all).
-- Run this file in the Supabase SQL editor if you prefer to create them yourself.
--
-- Security model: the browser never talks to the database. All reads and writes go through the
-- Baton API, which checks project membership, role and access label (Team/Leads/Restricted) in every
-- query. Row-Level Security is switched ON for every table with NO policies, so Supabase's public
-- REST API (anon / authenticated keys) can read nothing. Only the API's database user can.
-- Passwords are stored only as salted scrypt hashes; invite links only as SHA-256 hashes.
"""
d = postgresql.dialect()
out = [HEAD]
for t in Base.metadata.sorted_tables:
    out.append(str(CreateTable(t, if_not_exists=True).compile(dialect=d)).strip() + ";")
    for ix in sorted(t.indexes, key=lambda i: i.name):
        out.append(str(CreateIndex(ix, if_not_exists=True).compile(dialect=d)).strip() + ";")
    out.append("")
out.append("-- Row-Level Security: deny everything to the public Supabase roles.")
out += [f"ALTER TABLE {t.name} ENABLE ROW LEVEL SECURITY;" for t in Base.metadata.sorted_tables]
out += ["", "-- The audit log is append-only: nobody (except a superuser) may change or delete history.",
        "REVOKE UPDATE, DELETE ON audit_events FROM PUBLIC, anon, authenticated;", ""]
(Path(__file__).resolve().parent.parent / "sql" / "schema.sql").write_text("\n".join(out), encoding="utf-8")
print("wrote sql/schema.sql with", len(Base.metadata.sorted_tables), "tables")
