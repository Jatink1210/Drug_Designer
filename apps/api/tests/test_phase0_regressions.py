"""Phase 0 regression coverage for local desktop runtime fixes."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import models.db_tables  # noqa: F401
import models.user  # noqa: F401
from core.db import Base, get_db
from core.env_bootstrap import load_runtime_env
from main import app
from middleware import rate_limit
from middleware.rate_limit import _windows
from models.db_tables import UserPreference
from models.user import User


@pytest_asyncio.fixture
async def session_factory(tmp_path: Path):
    db_path = tmp_path / "phase0-regressions.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    _windows.clear()
    try:
        yield factory
    finally:
        app.dependency_overrides.clear()
        _windows.clear()
        await engine.dispose()


@pytest_asyncio.fixture
async def client(session_factory):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_desktop_bypass_settings_persist_local_owner(client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch):
    """Desktop bypass must create the persisted local owner before FK-backed settings writes."""
    monkeypatch.setenv("DRUGDESIGNER_AUTH_ENABLED", "false")

    payload = {
        "compute_mode": "cpu",
        "runtime": "airllm",
        "model_id": "Gemma-4-26B-A4B",
        "remote_base_url": "",
        "privacy_mode": True,
        "setup_complete": True,
    }

    response = await client.post("/api/v1/settings", json=payload)
    assert response.status_code == 200

    async with session_factory() as session:
        user = await session.get(User, "local_desktop")
        assert user is not None

        pref = (
            await session.execute(
                select(UserPreference).where(UserPreference.user_id == "local_desktop")
            )
        ).scalars().one()
        assert pref.default_runtime_mode == "airllm"
        assert pref.preferences_json["setup_complete"] is True


@pytest.mark.asyncio
async def test_local_desktop_browsing_uses_authenticated_rate_limit(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """Desktop browsing must stay on the authenticated limiter path, not the 10/min anonymous bucket."""
    monkeypatch.setenv("DRUGDESIGNER_AUTH_ENABLED", "false")
    monkeypatch.setattr(rate_limit, "AUTHENTICATED_LIMIT", 12)
    monkeypatch.setattr(rate_limit, "UNAUTHENTICATED_LIMIT", 3)
    monkeypatch.setattr(rate_limit, "WINDOW_SECONDS", 60)
    _windows.clear()

    responses = [await client.get("/api/v1/settings") for _ in range(12)]

    assert all(response.status_code == 200 for response in responses)
    assert {response.headers["X-RateLimit-Limit"] for response in responses} == {"12"}

    limited = await client.get("/api/v1/settings")
    assert limited.status_code == 429
    assert limited.headers["X-RateLimit-Limit"] == "12"


def test_load_runtime_env_preserves_existing_process_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Docker/shell env must beat local `.env` defaults."""
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("DSS_MODE=workbench\nDSS_STORAGE_BACKEND=embedded\n", encoding="utf-8")

    monkeypatch.setenv("DSS_MODE", "studio")
    monkeypatch.setenv("DSS_STORAGE_BACKEND", "full")

    load_runtime_env(dotenv_path)

    assert os.environ["DSS_MODE"] == "studio"
    assert os.environ["DSS_STORAGE_BACKEND"] == "full"