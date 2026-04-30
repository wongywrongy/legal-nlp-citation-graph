"""
Pytest fixtures: synthetic PDFs (built with PyMuPDF in-memory), DB sessions
(sync + async, each backed by aiosqlite/sqlite over the same temp file),
and a FastAPI TestClient that wires both dependencies into the temp DB.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import fitz  # PyMuPDF
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker


# ---- Environment isolation ---------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("DATABASE_URL_SYNC", f"sqlite:///{db_path}")
    monkeypatch.setenv("PDF_STORAGE_PATH", str(tmp_path / "pdfs"))
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/15")
    monkeypatch.setenv("FEATURE_LLM_RESOLVER", "false")
    monkeypatch.setenv("FEATURE_EXTERNAL_ENRICHMENT", "false")
    monkeypatch.setenv("FEATURE_EMBEDDINGS", "false")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    yield


# ---- Synthetic PDFs ---------------------------------------------------------


def _build_pdf(path: Path, pages: list[str]) -> Path:
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=11)
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def make_pdf(tmp_path: Path):
    def _make(name: str, pages: list[str]) -> Path:
        return _build_pdf(tmp_path / name, pages)

    return _make


@pytest.fixture
def roe_pdf(make_pdf) -> Path:
    return make_pdf(
        "roe.pdf",
        ["Cited in Roe v. Wade, 410 U.S. 113 (1973), and elsewhere."],
    )


@pytest.fixture
def multi_citation_pdf(make_pdf) -> Path:
    return make_pdf(
        "multi.pdf",
        [
            "See Brown v. Board of Education, 347 U.S. 483 (1954). "
            "Then later, Miranda v. Arizona, 384 U.S. 436 (1966).",
            "Cf. Marbury v. Madison, 5 U.S. 137 (1803).",
        ],
    )


# ---- Test DB + FastAPI client ------------------------------------------------


@pytest.fixture
def test_db(tmp_path):
    """
    Provide a single SQLite file backing both the sync and async sessions.
    Wires FastAPI's `get_db` and `get_async_db` to override the production
    engines — important since `main.py` routes depend on `get_async_db`.
    """
    from backend.database import get_async_db, get_db
    from backend.main import app
    from backend.models import Base

    db_path = tmp_path / "client.db"
    sync_url = f"sqlite:///{db_path}"
    async_url = f"sqlite+aiosqlite:///{db_path}"

    sync_engine = create_engine(sync_url)
    SyncSession = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)
    Base.metadata.create_all(bind=sync_engine)

    async_engine = create_async_engine(async_url)
    AsyncSession = async_sessionmaker(async_engine, expire_on_commit=False)

    def _override_sync():
        db = SyncSession()
        try:
            yield db
        finally:
            db.close()

    async def _override_async():
        async with AsyncSession() as session:
            yield session

    app.dependency_overrides[get_db] = _override_sync
    app.dependency_overrides[get_async_db] = _override_async

    yield sync_engine

    app.dependency_overrides.clear()


@pytest.fixture
def client(test_db) -> Iterator[TestClient]:
    from backend.main import app

    with TestClient(app) as c:
        yield c


# ---- Test fixture data -------------------------------------------------------


@pytest.fixture
def sample_citation_text() -> str:
    return "Roe v. Wade, 410 U.S. 113 (1973)."


@pytest.fixture
def test_document_data() -> dict:
    return {
        "title": "Test Legal Document",
        "fingerprint": "test_fingerprint_123",
        "source_path": "/test/path/document.pdf",
        "court": "U.S. Supreme Court",
        "year": 1973,
        "docket": "71-1234",
    }


@pytest.fixture
def test_citation_data() -> dict:
    return {
        "raw_text": "410 U.S. 113 (1973)",
        "normalized_key": "U.S._410_113_1973",
        "reporter": "U.S.",
        "volume": 410,
        "page": 113,
        "year": 1973,
        "confidence": 0.95,
    }
