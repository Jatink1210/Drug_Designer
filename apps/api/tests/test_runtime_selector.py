"""Tests for the RuntimeSelector hardware detector and runtime registry."""

import pytest
from services.runtime.selector import RuntimeSelector


@pytest.fixture(autouse=True)
def _reset():
    RuntimeSelector.reset()
    yield
    RuntimeSelector.reset()


def test_detect_capabilities_returns_cpu_cores():
    caps = RuntimeSelector.detect_capabilities()
    assert isinstance(caps["cpu_cores"], int)
    assert caps["cpu_cores"] > 0


def test_detect_capabilities_keys():
    caps = RuntimeSelector.detect_capabilities()
    expected_keys = {"cpu_cores", "gpu", "gpu_name", "airllm_installed", "ram_gb"}
    assert expected_keys.issubset(set(caps.keys()))


def test_get_available_runtimes_count():
    runtimes = RuntimeSelector.get_available_runtimes()
    assert len(runtimes) == 3


def test_get_available_runtimes_ids():
    runtimes = RuntimeSelector.get_available_runtimes()
    ids = {r["id"] for r in runtimes}
    assert ids == {"llama.cpp", "airllm", "remote"}


def test_get_available_runtimes_structure():
    runtimes = RuntimeSelector.get_available_runtimes()
    required_keys = {"id", "name", "status", "capabilities"}
    for rt in runtimes:
        assert required_keys.issubset(set(rt.keys())), f"Runtime {rt.get('id')} missing keys"


def test_get_active_runtime_returns_llama_cpp(tmp_store):
    from services.runtime.llama_cpp import LlamaCppRuntime
    runtime = RuntimeSelector.get_active_runtime()
    assert isinstance(runtime, LlamaCppRuntime)


def test_airllm_status_reflects_availability():
    from services.runtime.airllm import IS_AIRLLM_AVAILABLE
    runtimes = RuntimeSelector.get_available_runtimes()
    airllm_rt = next(r for r in runtimes if r["id"] == "airllm")
    if IS_AIRLLM_AVAILABLE:
        assert airllm_rt["status"] == "ready"
    else:
        assert airllm_rt["status"] == "not_installed"


def test_remote_runtime_always_ready():
    runtimes = RuntimeSelector.get_available_runtimes()
    remote_rt = next(r for r in runtimes if r["id"] == "remote")
    assert remote_rt["status"] == "ready"
