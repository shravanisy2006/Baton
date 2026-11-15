"""Database engine and session. SQLite for local runs and tests, Supabase Postgres in production."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    # Supabase gives postgres:// or postgresql:// URLs; use the psycopg (v3) driver explicitly.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg://" + url[len(prefix) :]
    kwargs = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # Supabase's connection pooler doesn't support server-side prepared statements.
        kwargs["connect_args"] = {"prepare_threshold": None}
    try:
        return create_engine(url, **kwargs)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(
            "DATABASE_URL in backend/.env is not a valid database address. Leave it empty to use a local file, "
            "or paste the Supabase 'Session pooler' URI. If your database password contains @ # / or %, "
            "reset it in Supabase to one with only letters and numbers."
        ) from e


engine = _make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Bring the database to the current schema with Alembic migrations (backend/migrations).

    - New database: every migration runs.
    - Database made by a version before migrations existed (tables but no alembic_version): any missing
      columns are added the old way, it is marked as the Round 3 baseline (0001), then newer migrations run.
    """
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    from . import models  # noqa: F401  (register tables)
    from .config import BACKEND_DIR

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    tables = set(inspect(engine).get_table_names())
    if tables and "alembic_version" not in tables:
        _add_missing_columns()
        with engine.begin() as conn:
            cfg.attributes["connection"] = conn
            command.stamp(cfg, "0001")
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
    _load_demo_cache()


# Added by migration 0002 (with proper defaults), so the legacy routine below leaves them to it.
_MIGRATION_0002_COLUMNS = {
    ("users", "session_version"),
    ("users", "email_verified_at"),
    ("users", "deleted_at"),
    ("jobs", "actor_id"),
    ("jobs", "attempts"),
    ("jobs", "started_at"),
    ("evidence_units", "flags"),
    ("claims", "topic"),
}


def _add_missing_columns() -> None:
    """Legacy upgrade path (before Alembic): add Round 2/3 columns an older database lacks (no data is lost)."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name not in have and (table.name, col.name) not in _MIGRATION_0002_COLUMNS:
                    ddl = col.type.compile(dialect=engine.dialect)
                    conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {col.name} {ddl}"))
                    if (table.name, col.name) == ("evidence_units", "analysed_at"):
                        # Evidence in projects that were already analysed counts as analysed, so the first
                        # "Analyse new evidence" after the upgrade doesn't redo everything.
                        conn.execute(
                            text(
                                "UPDATE evidence_units SET analysed_at = CURRENT_TIMESTAMP WHERE project_id IN "
                                "(SELECT project_id FROM jobs WHERE status = 'done')"
                            )
                        )


def _load_demo_cache() -> None:
    """Preload saved AI responses for the synthetic demo so a fresh deploy needs no AI quota for it."""
    import json
    import os

    from .config import BACKEND_DIR
    from .models import LLMCache

    path = BACKEND_DIR / "seed" / "eventapp" / "llm_cache.json"
    if os.environ.get("BATON_SKIP_DEMO_CACHE") or not path.exists():
        return
    rows = json.loads(path.read_text(encoding="utf-8"))
    with SessionLocal() as db:
        have = {k for (k,) in db.query(LLMCache.key).filter(LLMCache.key.in_([r["key"] for r in rows]))}
        for r in rows:
            if r["key"] not in have:
                db.add(LLMCache(key=r["key"], task=r["task"], model=r["model"], response=r["response"]))
        db.commit()
