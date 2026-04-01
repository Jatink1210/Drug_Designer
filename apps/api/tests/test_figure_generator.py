"""Tests for figure_generator.py — file output verification."""
from __future__ import annotations

import os
from unittest.mock import patch

from services.figure_generator import FigureGenerator


def test_generate_network_graph_creates_files(tmp_store, job_logger_cls):
    with patch.object(job_logger_cls, "log_artifact"):
        FigureGenerator.generate_network_graph("test_job_001")

    media_dir = os.path.join(tmp_store, "media")
    files = os.listdir(media_dir)
    svg_files = [f for f in files if f.endswith(".svg")]
    png_files = [f for f in files if f.endswith(".png")]
    json_files = [f for f in files if f.endswith(".json")]
    assert len(svg_files) >= 1, "Expected at least one SVG file"
    assert len(png_files) >= 1, "Expected at least one PNG file"
    assert len(json_files) >= 1, "Expected at least one JSON file"


def test_generate_heatmap_creates_files(tmp_store, job_logger_cls):
    with patch.object(job_logger_cls, "log_artifact"):
        FigureGenerator.generate_heatmap("test_job_002")

    media_dir = os.path.join(tmp_store, "media")
    files = os.listdir(media_dir)
    svg_files = [f for f in files if f.endswith(".svg")]
    png_files = [f for f in files if f.endswith(".png")]
    assert len(svg_files) >= 1
    assert len(png_files) >= 1


def test_generate_waterfall_creates_files(tmp_store, job_logger_cls):
    with patch.object(job_logger_cls, "log_artifact"):
        FigureGenerator.generate_waterfall("test_job_003")

    media_dir = os.path.join(tmp_store, "media")
    files = os.listdir(media_dir)
    svg_files = [f for f in files if f.endswith(".svg")]
    assert len(svg_files) >= 1


def test_save_json_creates_file(tmp_store):
    path = FigureGenerator._save_json(
        {"key": "value", "numbers": [1, 2, 3]},
        "test_job_004",
        "metadata",
    )
    assert os.path.exists(path)
    assert path.endswith(".json")
