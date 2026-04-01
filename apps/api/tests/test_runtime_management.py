"""Tests for Phase 9 — Advanced Runtime Management.

Covers: recommend_compute_mode, recommend_model, _load_catalog,
compatibility checks, settings sync, compute_mode persistence,
and the /recommend endpoint.
"""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app
from services.runtime.selector import RuntimeSelector

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_runtime():
    RuntimeSelector.reset()
    yield
    RuntimeSelector.reset()


# ── recommend_compute_mode ────────────────────────────────────

def test_recommend_compute_mode_no_gpu():
    """Returns 'cpu' when no GPU is detected."""
    caps = {
        "cpu_cores": 8, "ram_gb": 16, "gpu": "none",
        "gpu_name": None, "vram_gb": 0, "airllm_installed": False,
    }
    with patch.object(RuntimeSelector, "detect_capabilities", return_value=caps):
        assert RuntimeSelector.recommend_compute_mode() == "cpu"


def test_recommend_compute_mode_with_cuda():
    """Returns 'gpu' when CUDA GPU with sufficient VRAM is available."""
    caps = {
        "cpu_cores": 8, "ram_gb": 32, "gpu": "cuda",
        "gpu_name": "NVIDIA RTX 3090", "vram_gb": 24, "airllm_installed": False,
    }
    with patch.object(RuntimeSelector, "detect_capabilities", return_value=caps):
        assert RuntimeSelector.recommend_compute_mode() == "gpu"


def test_recommend_compute_mode_with_mps():
    """Returns 'gpu' when Apple Silicon MPS is available."""
    caps = {
        "cpu_cores": 10, "ram_gb": 16, "gpu": "mps",
        "gpu_name": "Apple Silicon", "vram_gb": 0, "airllm_installed": False,
    }
    with patch.object(RuntimeSelector, "detect_capabilities", return_value=caps):
        assert RuntimeSelector.recommend_compute_mode() == "gpu"


# ── recommend_model ───────────────────────────────────────────

def test_recommend_model_cpu():
    """Recommends a compatible small model for CPU mode."""
    caps = {
        "cpu_cores": 8, "ram_gb": 16, "gpu": "none",
        "gpu_name": None, "vram_gb": 0, "airllm_installed": False,
    }
    with patch.object(RuntimeSelector, "detect_capabilities", return_value=caps):
        result = RuntimeSelector.recommend_model("cpu")

    assert result["compute_mode"] == "cpu"
    assert result["recommended_model"] is not None
    # With 16 GB RAM, should recommend BioMistral-7B (biomedical, 8 GB min_ram)
    assert result["recommended_model"]["name"] == "BioMistral-7B"
    # Meditron-70B (min_ram 48) should be excluded
    names = [m["name"] for m in result["compatible_models"]]
    assert "Meditron-70B" not in names


def test_recommend_model_gpu():
    """Recommends a GPU-capable model when CUDA with sufficient VRAM."""
    caps = {
        "cpu_cores": 8, "ram_gb": 32, "gpu": "cuda",
        "gpu_name": "RTX 3090", "vram_gb": 24, "airllm_installed": False,
    }
    with patch.object(RuntimeSelector, "detect_capabilities", return_value=caps):
        result = RuntimeSelector.recommend_model("gpu")

    assert result["compute_mode"] == "gpu"
    assert result["recommended_model"] is not None
    # Meditron-70B requires 24 GB VRAM — should be included
    names = [m["name"] for m in result["compatible_models"]]
    assert "Meditron-70B" in names


def test_recommend_model_no_compatible():
    """Falls back to smallest models when none match hardware."""
    caps = {
        "cpu_cores": 2, "ram_gb": 1, "gpu": "none",
        "gpu_name": None, "vram_gb": 0, "airllm_installed": False,
    }
    with patch.object(RuntimeSelector, "detect_capabilities", return_value=caps):
        result = RuntimeSelector.recommend_model("cpu")

    assert result["compute_mode"] == "cpu"
    # All models need > 1 GB RAM, fallback picks min_ram <= 8
    assert len(result["compatible_models"]) > 0
    # Fallback should include lightweight models
    names = [m["name"] for m in result["compatible_models"]]
    assert "PubMedBERT" in names  # min_ram 2 <= 8
    assert "Phi-3-mini-4k" in names  # min_ram 4 <= 8


# ── _load_catalog ─────────────────────────────────────────────

def test_load_catalog():
    """Loads and parses models_catalog.json correctly."""
    catalog = RuntimeSelector._load_catalog()
    assert isinstance(catalog, list)
    assert len(catalog) >= 6
    for m in catalog:
        assert "name" in m
        assert "size_gb" in m
        assert "min_ram_gb" in m
        assert "min_vram_gb" in m
        assert "compute_modes" in m


# ── compatibility check (router endpoint) ─────────────────────

def test_compatibility_check_sufficient_ram():
    """GET /api/models/compatibility returns cpu_compatible=True with enough RAM."""
    caps = {
        "cpu_cores": 8, "ram_gb": 16, "gpu": "none",
        "gpu_name": None, "vram_gb": 0, "airllm_installed": False,
    }
    with patch.object(RuntimeSelector, "detect_capabilities", return_value=caps):
        resp = client.get("/api/models/compatibility/BioMistral-7B")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cpu_compatible"] is True
    assert data["model"] == "BioMistral-7B"


def test_compatibility_check_insufficient_vram():
    """GET /api/models/compatibility returns gpu_compatible=False with low VRAM."""
    caps = {
        "cpu_cores": 8, "ram_gb": 16, "gpu": "cuda",
        "gpu_name": "GTX 1060", "vram_gb": 3, "airllm_installed": False,
    }
    with patch.object(RuntimeSelector, "detect_capabilities", return_value=caps):
        resp = client.get("/api/models/compatibility/BioMistral-7B")
    assert resp.status_code == 200
    data = resp.json()
    assert data["gpu_compatible"] is False
    assert data["requirements"]["min_vram_gb"] == 6


# ── settings sync ─────────────────────────────────────────────

def test_settings_sync_runtime(tmp_store):
    """POST /api/settings syncs RuntimeSelector config."""
    resp = client.post("/api/settings", json={
        "compute_mode": "gpu",
        "runtime": "remote",
        "model_id": "Llama-3-8B-Instruct",
        "remote_base_url": "https://api.example.com/v1",
        "privacy_mode": True,
        "setup_complete": True,
    })
    assert resp.status_code == 200

    # RuntimeSelector should have been synced
    config_path = RuntimeSelector._config_path()
    assert os.path.exists(config_path)
    with open(config_path) as f:
        data = json.load(f)
    assert data["runtime_id"] == "remote"
    assert data["model_name"] == "Llama-3-8B-Instruct"
    assert data["compute_mode"] == "gpu"


# ── compute_mode persistence ──────────────────────────────────

def test_compute_mode_persists(tmp_store):
    """compute_mode is saved to and loaded from runtime_config.json."""
    RuntimeSelector.set_active_runtime(
        runtime_id="llama.cpp",
        model_name="BioMistral-7B",
        compute_mode="gpu",
    )
    assert RuntimeSelector.get_compute_mode() == "gpu"

    # Change to auto
    RuntimeSelector.set_active_runtime(
        runtime_id="llama.cpp",
        model_name="PubMedBERT",
        compute_mode="auto",
    )
    assert RuntimeSelector.get_compute_mode() == "auto"


# ── /recommend endpoint ───────────────────────────────────────

def test_recommend_endpoint():
    """GET /api/runtimes/recommend returns recommendation structure."""
    caps = {
        "cpu_cores": 8, "ram_gb": 16, "gpu": "none",
        "gpu_name": None, "vram_gb": 0, "airllm_installed": False,
    }
    with patch.object(RuntimeSelector, "detect_capabilities", return_value=caps):
        resp = client.get("/api/runtimes/recommend")
    assert resp.status_code == 200
    data = resp.json()
    assert "compute_mode" in data
    assert "recommended_model" in data
    assert "compatible_models" in data
    assert "hardware" in data
    assert isinstance(data["compatible_models"], list)
