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
            url = "postgresql+psycopg://" + url[len(prefix):]
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
    from . import models  # noqa: F401  (register tables)

    Base.metadata.create_all(bind=engine)
    _add_missing_columns()
    _load_demo_cache()


def _add_missing_columns() -> None:
    """Upgrade an existing database in place when a new version adds columns (no data is lost)."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name not in have:
                    ddl = col.type.compile(dialect=engine.dialect)
                    conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN {col.name} {ddl}'))
                    if (table.name, col.name) == ("evidence_units", "analysed_at"):
                        # Evidence in projects that were already analysed counts as analysed, so the first
                        # "Analyse new evidence" after the upgrade doesn't redo everything.
                        conn.execute(text(
                            "UPDATE evidence_units SET analysed_at = CURRENT_TIMESTAMP WHERE project_id IN "
                            "(SELECT project_id FROM jobs WHERE status = 'done')"))


def _load_demo_cache() -> None:
    """Preload saved AI responses for the synthetic demo so a fresh deploy needs no AI quota for it."""
    import json

    from .config import BACKEND_DIR
    from .models import LLMCache

    import os

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
