"""Tests for LLM runtime (llama_cpp, selector, config persistence)."""

import json
import os
import pytest

from services.runtime.llama_cpp import LlamaCppRuntime
from services.runtime.selector import RuntimeSelector
from services.runtime.remote_openai import RemoteOpenAIRuntime


@pytest.fixture(autouse=True)
def _reset_runtime():
    RuntimeSelector.reset()
    yield
    RuntimeSelector.reset()


def test_llama_cpp_health_check_without_ollama():
    """Health check returns FAIL when Ollama is not running."""
    rt = LlamaCppRuntime(endpoint="http://localhost:99999")
    h = rt.health_check()
    assert h["status"] == "FAIL"
    assert h["type"] == "llama_cpp"


def test_llama_cpp_capabilities():
    rt = LlamaCppRuntime()
    assert "chat" in rt.capabilities
    assert "embeddings" in rt.capabilities
    assert "local" in rt.capabilities


def test_llama_cpp_delegates_to_remote():
    """LlamaCppRuntime uses RemoteOpenAIRuntime as delegate."""
    rt = LlamaCppRuntime(endpoint="http://localhost:11434", model="test-model")
    assert isinstance(rt._delegate, RemoteOpenAIRuntime)
    assert rt._delegate.base_url == "http://localhost:11434/v1"
    assert rt._delegate.model == "test-model"


@pytest.mark.asyncio
async def test_llama_cpp_chat_graceful_failure():
    """Chat returns fallback message when Ollama is unavailable."""
    rt = LlamaCppRuntime(endpoint="http://localhost:99999")
    result = await rt.chat([{"role": "user", "content": "hello"}])
    assert "[LLM unavailable:" in result


@pytest.mark.asyncio
async def test_llama_cpp_embeddings_graceful_failure():
    """Embeddings return empty list when Ollama is unavailable."""
    rt = LlamaCppRuntime(endpoint="http://localhost:99999")
    result = await rt.embeddings(["test text"])
    assert result == []


def test_selector_config_persistence(tmp_store):
    """set_active_runtime persists config to runtime_config.json."""
    RuntimeSelector.set_active_runtime(
        runtime_id="remote",
        model_name="gpt-4o",
        endpoint="https://api.example.com/v1",
        api_key="sk-secret-123",
    )
    config_path = RuntimeSelector._config_path()
    assert os.path.exists(config_path)
    with open(config_path) as f:
        data = json.load(f)
    assert data["runtime_id"] == "remote"
    assert data["model_name"] == "gpt-4o"
    # api_key must NOT be persisted
    assert "api_key" not in data


def test_selector_loads_persisted_config(tmp_store):
    """get_active_runtime reads from persisted config."""
    config_path = RuntimeSelector._config_path()
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w") as f:
        json.dump({"runtime_id": "llama.cpp", "model_name": "phi3", "endpoint": ""}, f)

    rt = RuntimeSelector.get_active_runtime()
    assert isinstance(rt, LlamaCppRuntime)
    assert rt.model == "phi3"


def test_selector_default_without_config(tmp_store):
    """Without config file, get_active_runtime returns llama.cpp default."""
    rt = RuntimeSelector.get_active_runtime()
    assert isinstance(rt, LlamaCppRuntime)


def test_selector_get_active_runtime_id(tmp_store):
    """get_active_runtime_id returns the persisted runtime ID."""
    RuntimeSelector.set_active_runtime("remote", model_name="gpt-4o-mini")
    assert RuntimeSelector.get_active_runtime_id() == "remote"
