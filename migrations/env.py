"""Alembic runner. Never imports app.main (startup auto-creation is pilot only)."""
from __future__ import annotations
import os
from alembic import context
from sqlalchemy import create_engine, pool

def get_url():
    value = os.environ.get("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL must be set explicitly for schema migrations")
    if value.startswith("postgres://"):
        value = value.replace("postgres://", "postgresql+psycopg://", 1)
    elif value.startswith("postgresql://"):
        value = value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value

if context.is_offline_mode():
    context.configure(url=get_url(), literal_binds=True, dialect_opts={"paramstyle":"named"})
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(get_url(), poolclass=pool.NullPool, pool_pre_ping=True)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=None,
                          compare_type=True, transactional_ddl=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
