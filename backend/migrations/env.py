"""Alembic environment: uses Baton's own engine (DATABASE_URL) and models."""

from alembic import context

from app import models  # noqa: F401  (register tables)
from app.db import Base, engine

target_metadata = Base.metadata


def run_migrations_online() -> None:
    connection = context.config.attributes.get("connection")
    if connection is not None:  # called from app.db.init_db with an open connection
        _run(connection)
    else:  # command line: alembic upgrade head
        with engine.connect() as connection:
            _run(connection)
            connection.commit()


def _run(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=connection.dialect.name == "sqlite",
        compare_type=False,
    )
    with context.begin_transaction():
        context.run_migrations()


run_migrations_online()
