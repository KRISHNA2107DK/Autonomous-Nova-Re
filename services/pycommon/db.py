"""SQLAlchemy engine/session factory shared by the Python services."""

from __future__ import annotations

import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker


def database_url(default_db: str) -> str:
    host = os.getenv("DB_HOST", "postgres-service")
    port = os.getenv("DB_PORT", "5432")
    user = os.getenv("DB_USER", "novasurge")
    password = os.getenv("DB_PASSWORD", "")
    name = os.getenv("DB_NAME", default_db)
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


def make_engine(default_db: str):
    return create_engine(
        database_url(default_db),
        pool_pre_ping=True,
        pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
        pool_timeout=5,
        connect_args={"connect_timeout": 3},
    )


def ping(engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


Base = declarative_base()

# Arbitrary constant: every replica of every service serialises schema setup on it.
_SCHEMA_LOCK_ID = 7_310_001


def create_schema(engine, seed=None) -> None:
    """
    Create tables (and optionally seed) under a transaction-scoped advisory lock.

    Replicas start concurrently; without the lock two `CREATE TABLE` statements
    race on Postgres' catalog unique index and one replica crashes, and a
    check-then-insert seeder can seed twice.
    """
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": _SCHEMA_LOCK_ID})
        Base.metadata.create_all(bind=conn)
        if seed is not None:
            seed(conn)


def session_factory(engine):
    return sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
