"""Shared runtime policy helpers for hosted-vs-local LLM behavior."""

from __future__ import annotations

import os
from typing import Any, Dict

from config import settings


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def get_runtime_mode() -> str:
    mode = (os.getenv("LLM_RUNTIME_MODE") or settings.llm_runtime_mode or "hosted").strip().lower()
    if mode not in {"hosted", "local", "auto"}:
        return "hosted"
    return mode


def get_remote_base_url() -> str:
    return (
        os.getenv("OPENAI_API_BASE")
        or os.getenv("LLM_API_BASE")
        or settings.llm_remote_base_url
        or "https://api.openai.com/v1"
    ).rstrip("/")


def get_remote_api_key() -> str:
    return os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY") or settings.openai_api_key or ""


def ollama_enabled() -> bool:
    return _env_bool("LLM_ENABLE_OLLAMA", bool(settings.llm_enable_ollama)) or get_runtime_mode() == "local"


def airllm_enabled() -> bool:
    return _env_bool("AIRLLM_ENABLED", bool(settings.airllm_enabled))


def allow_local_backends() -> bool:
    return get_runtime_mode() == "local"


def default_runtime_id() -> str:
    return "llama.cpp" if allow_local_backends() else "remote"


def default_model_name() -> str:
    return settings.ollama_model if allow_local_backends() else settings.openai_model


def hosted_runtime_configured() -> bool:
    return bool(get_remote_api_key() or os.getenv("OPENAI_API_BASE") or os.getenv("LLM_API_BASE") or settings.llm_remote_base_url)


def get_runtime_policy() -> Dict[str, Any]:
    mode = get_runtime_mode()
    return {
        "mode": mode,
        "default_runtime": default_runtime_id(),
        "default_model": default_model_name(),
        "remote_base_url": get_remote_base_url(),
        "hosted_runtime_configured": hosted_runtime_configured(),
        "ollama_enabled": ollama_enabled(),
        "ollama_base_url": settings.ollama_host,
        "airllm_enabled": airllm_enabled(),
        "local_backends_allowed": allow_local_backends(),
    }