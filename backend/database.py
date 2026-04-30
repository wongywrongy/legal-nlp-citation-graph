"""
Database session management.

Two engines coexist:
  - sync engine + SessionLocal  : used by Alembic migrations and the legacy
    DocumentProcessor pipeline (Phase 1).
  - async engine + AsyncSessionLocal : used by FastAPI route handlers and
    ARQ workers (Phase 2).
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.config import settings

_sync_kwargs = {}
if settings.database_url_sync.startswith("sqlite"):
    _sync_kwargs.update(
        {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
    )

engine = create_engine(settings.database_url_sync, echo=False, **_sync_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency that yields a sync session (legacy)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_async_kwargs = {}
if settings.database_url.startswith("sqlite"):
    _async_kwargs["connect_args"] = {"check_same_thread": False}

async_engine = create_async_engine(settings.database_url, echo=False, **_async_kwargs)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)


async def get_async_db():
    """FastAPI dependency that yields an AsyncSession."""
    async with AsyncSessionLocal() as session:
        yield session


def create_tables() -> None:
    """Legacy bootstrap — prefer Alembic in production."""
    from backend.models import Base

    Base.metadata.create_all(bind=engine)
