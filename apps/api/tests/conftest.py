"""Shared test fixtures for the API backend test suite."""

import os
import pytest

from config import settings
from services.job_logger import JobLogger
from services.evidence_store import EvidenceStore


@pytest.fixture
def tmp_store(tmp_path, monkeypatch):
    """Redirect all service SQLite databases to a temporary directory.

    Services evaluate ``_db_path`` at class-definition time (import time),
    so we must monkeypatch the class attributes directly.
    """
    store_dir = str(tmp_path)
    monkeypatch.setattr(settings, "local_store_path", store_dir)
    monkeypatch.setattr(JobLogger, "_db_path", str(tmp_path / "job_logs.db"))
    monkeypatch.setattr(EvidenceStore, "_db_path", str(tmp_path / "evidence_cache.db"))

    # DocTreeService may fail to import if pymupdf is missing — patch only if importable
    try:
        from services.doc_tree import DocTreeService
        monkeypatch.setattr(DocTreeService, "_db_path", str(tmp_path / "doctree_index.db"))
    except ImportError:
        pass

    # Reset the vector store singleton so it picks up the patched local_store_path
    from core.vector_store import reset_vector_store
    reset_vector_store()

    # Reset the graph store singleton
    from services.graph_store import reset_graph_store
    reset_graph_store()

    return store_dir


@pytest.fixture
def evidence_store(tmp_store):
    """Return the EvidenceStore class with a clean database."""
    EvidenceStore.setup_db()
    return EvidenceStore


@pytest.fixture
def job_logger_cls(tmp_store):
    """Return the JobLogger class with a clean database."""
    JobLogger.setup_db()
    return JobLogger
