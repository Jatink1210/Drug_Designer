"""Unit tests for DockingService enhancements (Task 6.3).

Tests input validation, _find_executable with tools/bin, and _parse_vina_output.
"""

import os
import sys
import tempfile
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "apps", "api"))

from apps.api.services.docking_service import DockingService


class TestValidateDockingInputs:
    """Tests for DockingService.validate_docking_inputs()."""

    def test_valid_inputs_return_none(self):
        err = DockingService.validate_docking_inputs(
            receptor_path="/path/to/receptor.pdbqt",
            ligand_path="/path/to/ligand.pdbqt",
            center=[10.0, 20.0, 30.0],
            box_size=[20.0, 20.0, 20.0],
        )
        assert err is None

    def test_missing_receptor_path(self):
        err = DockingService.validate_docking_inputs(
            receptor_path="",
            ligand_path="/path/to/ligand.pdbqt",
            center=[10.0, 20.0, 30.0],
            box_size=[20.0, 20.0, 20.0],
        )
        assert err is not None
        assert "receptor_path" in err

    def test_missing_ligand_path(self):
        err = DockingService.validate_docking_inputs(
            receptor_path="/path/to/receptor.pdbqt",
            ligand_path="",
            center=[10.0, 20.0, 30.0],
            box_size=[20.0, 20.0, 20.0],
        )
        assert err is not None
        assert "ligand_path" in err

    def test_center_wrong_length(self):
        err = DockingService.validate_docking_inputs(
            receptor_path="/path/to/receptor.pdbqt",
            ligand_path="/path/to/ligand.pdbqt",
            center=[10.0, 20.0],
            box_size=[20.0, 20.0, 20.0],
        )
        assert err is not None
        assert "center" in err

    def test_box_size_wrong_length(self):
        err = DockingService.validate_docking_inputs(
            receptor_path="/path/to/receptor.pdbqt",
            ligand_path="/path/to/ligand.pdbqt",
            center=[10.0, 20.0, 30.0],
            box_size=[20.0],
        )
        assert err is not None
        assert "box_size" in err

    def test_empty_center(self):
        err = DockingService.validate_docking_inputs(
            receptor_path="/path/to/receptor.pdbqt",
            ligand_path="/path/to/ligand.pdbqt",
            center=[],
            box_size=[20.0, 20.0, 20.0],
        )
        assert err is not None
        assert "center" in err

    def test_empty_box_size(self):
        err = DockingService.validate_docking_inputs(
            receptor_path="/path/to/receptor.pdbqt",
            ligand_path="/path/to/ligand.pdbqt",
            center=[10.0, 20.0, 30.0],
            box_size=[],
        )
        assert err is not None
        assert "box_size" in err

    def test_negative_box_size(self):
        err = DockingService.validate_docking_inputs(
            receptor_path="/path/to/receptor.pdbqt",
            ligand_path="/path/to/ligand.pdbqt",
            center=[10.0, 20.0, 30.0],
            box_size=[20.0, -5.0, 20.0],
        )
        assert err is not None
        assert "box_size" in err
        assert "positive" in err

    def test_zero_box_size(self):
        err = DockingService.validate_docking_inputs(
            receptor_path="/path/to/receptor.pdbqt",
            ligand_path="/path/to/ligand.pdbqt",
            center=[10.0, 20.0, 30.0],
            box_size=[20.0, 0.0, 20.0],
        )
        assert err is not None
        assert "positive" in err

    def test_whitespace_only_receptor_path(self):
        err = DockingService.validate_docking_inputs(
            receptor_path="   ",
            ligand_path="/path/to/ligand.pdbqt",
            center=[10.0, 20.0, 30.0],
            box_size=[20.0, 20.0, 20.0],
        )
        assert err is not None
        assert "receptor_path" in err

    def test_integer_values_in_center_accepted(self):
        err = DockingService.validate_docking_inputs(
            receptor_path="/path/to/receptor.pdbqt",
            ligand_path="/path/to/ligand.pdbqt",
            center=[10, 20, 30],
            box_size=[20, 20, 20],
        )
        assert err is None


class TestParseVinaOutput:
    """Tests for DockingService._parse_vina_output()."""

    def _write_pdbqt(self, content: str) -> str:
        """Write content to a temp PDBQT file and return the path."""
        fd, path = tempfile.mkstemp(suffix=".pdbqt")
        with os.fdopen(fd, "w") as f:
            f.write(content)
        return path

    def test_parse_single_pose(self):
        content = (
            "MODEL        1\n"
            "REMARK VINA RESULT    -7.5      0.000      0.000\n"
            "ATOM      1  C   LIG     1       0.000   0.000   0.000\n"
            "ENDMDL\n"
        )
        path = self._write_pdbqt(content)
        try:
            svc = DockingService.__new__(DockingService)
            poses = svc._parse_vina_output(path)
            assert len(poses) == 1
            assert poses[0]["rank"] == 1
            assert poses[0]["affinity_kcal"] == -7.5
            assert poses[0]["rmsd_lb"] == 0.0
            assert poses[0]["rmsd_ub"] == 0.0
        finally:
            os.unlink(path)

    def test_parse_multiple_poses(self):
        content = (
            "MODEL        1\n"
            "REMARK VINA RESULT    -7.5      0.000      0.000\n"
            "ENDMDL\n"
            "MODEL        2\n"
            "REMARK VINA RESULT    -6.8      1.234      2.567\n"
            "ENDMDL\n"
            "MODEL        3\n"
            "REMARK VINA RESULT    -5.2      3.456      4.789\n"
            "ENDMDL\n"
        )
        path = self._write_pdbqt(content)
        try:
            svc = DockingService.__new__(DockingService)
            poses = svc._parse_vina_output(path)
            assert len(poses) == 3
            assert poses[0]["rank"] == 1
            assert poses[1]["rank"] == 2
            assert poses[2]["rank"] == 3
            assert poses[1]["affinity_kcal"] == -6.8
            assert poses[1]["rmsd_lb"] == 1.234
            assert poses[1]["rmsd_ub"] == 2.567
        finally:
            os.unlink(path)

    def test_parse_empty_file(self):
        path = self._write_pdbqt("")
        try:
            svc = DockingService.__new__(DockingService)
            poses = svc._parse_vina_output(path)
            assert poses == []
        finally:
            os.unlink(path)

    def test_parse_nonexistent_file(self):
        svc = DockingService.__new__(DockingService)
        poses = svc._parse_vina_output("/nonexistent/path.pdbqt")
        assert poses == []

    def test_each_pose_has_all_fields(self):
        content = (
            "MODEL        1\n"
            "REMARK VINA RESULT    -8.1      0.000      0.000\n"
            "ENDMDL\n"
        )
        path = self._write_pdbqt(content)
        try:
            svc = DockingService.__new__(DockingService)
            poses = svc._parse_vina_output(path)
            pose = poses[0]
            assert "rank" in pose
            assert "affinity_kcal" in pose
            assert "rmsd_lb" in pose
            assert "rmsd_ub" in pose
            assert isinstance(pose["rank"], int)
            assert isinstance(pose["affinity_kcal"], float)
            assert isinstance(pose["rmsd_lb"], float)
            assert isinstance(pose["rmsd_ub"], float)
        finally:
            os.unlink(path)


class TestFindExecutable:
    """Tests for DockingService._find_executable() with tools/bin support."""

    @patch("shutil.which", return_value=None)
    def test_not_found_returns_none(self, _mock):
        svc = DockingService.__new__(DockingService)
        result = svc._find_executable("vina")
        assert result is None

    @patch("shutil.which", side_effect=lambda name: "/usr/bin/vina" if name == "vina" else None)
    def test_found_on_path(self, _mock):
        svc = DockingService.__new__(DockingService)
        result = svc._find_executable("vina")
        # _find_executable returns the candidate name that was found, not the full path
        assert result == "vina"

    def test_found_in_tools_bin(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            system = os.name
            vina_name = "vina.exe" if system == "nt" else "vina"
            vina_path = os.path.join(tmpdir, vina_name)
            with open(vina_path, "w") as f:
                f.write("#!/bin/sh\necho vina")
            os.chmod(vina_path, 0o755)

            svc = DockingService.__new__(DockingService)
            with patch("shutil.which", return_value=None):
                with patch("apps.api.services.docking_service._TOOLS_BIN_DIR", tmpdir):
                    result = svc._find_executable("vina")
                    assert result == vina_path
