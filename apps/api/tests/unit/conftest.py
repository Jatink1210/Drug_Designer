"""Pytest configuration and shared fixtures for unit tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock
from datetime import datetime
import uuid


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    redis.exists = AsyncMock(return_value=False)
    return redis


@pytest.fixture
def mock_qdrant():
    """Mock Qdrant vector store client."""
    qdrant = MagicMock()
    qdrant.search = MagicMock(return_value=[])
    qdrant.upsert = MagicMock()
    return qdrant


@pytest.fixture
def mock_neo4j():
    """Mock Neo4j graph database session."""
    neo4j = AsyncMock()
    neo4j.run = AsyncMock()
    neo4j.close = AsyncMock()
    return neo4j


@pytest.fixture
def sample_user_id():
    """Sample user ID."""
    return str(uuid.uuid4())


@pytest.fixture
def sample_project_id():
    """Sample project ID."""
    return str(uuid.uuid4())


@pytest.fixture
def sample_run_id():
    """Sample run ID."""
    return str(uuid.uuid4())


@pytest.fixture
def mock_llm_response():
    """Mock LLM response."""
    return {
        "choices": [
            {
                "message": {
                    "content": "Test response from LLM"
                }
            }
        ]
    }


@pytest.fixture
def mock_http_client():
    """Mock HTTP client."""
    client = AsyncMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    return client
