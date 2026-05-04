from __future__ import annotations

import pytest

from config import settings
from services.pico_extractor import extract_pico_data
from services.runtime.policy import get_runtime_policy
from services.runtime.selector import RuntimeSelector


def test_runtime_selector_defaults_to_remote_for_hosted_mode(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr(settings, "local_store_path", str(tmp_path))
    monkeypatch.setattr(settings, "llm_runtime_mode", "hosted")
    monkeypatch.setattr(settings, "llm_remote_base_url", "https://api.openai.com/v1")
    monkeypatch.delenv("LLM_RUNTIME_MODE", raising=False)
    monkeypatch.delenv("LLM_ENABLE_OLLAMA", raising=False)

    config = RuntimeSelector._load_config()

    assert config["runtime_id"] == "remote"
    assert config["model_name"] == settings.openai_model
    assert config["endpoint"] == "https://api.openai.com/v1"


@pytest.mark.asyncio
async def test_extract_pico_data_skips_ollama_when_disabled(monkeypatch: pytest.MonkeyPatch):
    async def fail_if_called(prompt: str):
        raise AssertionError("Ollama should not be called when disabled by policy")

    monkeypatch.setattr(settings, "llm_runtime_mode", "hosted")
    monkeypatch.setattr(settings, "llm_enable_ollama", False)
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr("services.pico_extractor._spacy_pico", lambda text: None)
    monkeypatch.setattr("services.pico_extractor._call_ollama", fail_if_called)

    result = await extract_pico_data(
        "Patients with glioblastoma were treated with temozolomide versus placebo and overall survival improved significantly."
    )

    assert result["method"] == "regex"
    assert result["diagnostics"]["llm_backend_attempted"] is False
    assert result["diagnostics"]["runtime_policy"]["ollama_enabled"] is False


def test_runtime_policy_reports_hosted_remote_defaults(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "llm_runtime_mode", "hosted")
    monkeypatch.setattr(settings, "llm_enable_ollama", False)
    monkeypatch.setattr(settings, "llm_remote_base_url", "https://api.openai.com/v1")
    monkeypatch.delenv("LLM_RUNTIME_MODE", raising=False)
    monkeypatch.delenv("LLM_ENABLE_OLLAMA", raising=False)

    policy = get_runtime_policy()

    assert policy["mode"] == "hosted"
    assert policy["default_runtime"] == "remote"
    assert policy["ollama_enabled"] is False