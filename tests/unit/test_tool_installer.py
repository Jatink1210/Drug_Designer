"""Unit tests for ToolInstaller service (Task 6.1, 6.3, 6.6)."""

import os
import sys
import tempfile
from unittest.mock import patch

import pytest

# Ensure apps/api is on the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "apps", "api"))

from apps.api.services.tool_installer import ToolInstaller, ToolStatus, InstallResult


class TestDetectOS:
    """Tests for ToolInstaller.detect_os()."""

    def test_returns_tuple_of_two_strings(self):
        system, machine = ToolInstaller.detect_os()
        assert isinstance(system, str)
        assert isinstance(machine, str)
        assert len(system) > 0
        assert len(machine) > 0

    @patch("apps.api.services.tool_installer.platform")
    def test_returns_linux_x86_64(self, mock_platform):
        mock_platform.system.return_value = "Linux"
        mock_platform.machine.return_value = "x86_64"
        system, machine = ToolInstaller.detect_os()
        assert system == "Linux"
        assert machine == "x86_64"

    @patch("apps.api.services.tool_installer.platform")
    def test_returns_darwin_arm64(self, mock_platform):
        mock_platform.system.return_value = "Darwin"
        mock_platform.machine.return_value = "arm64"
        system, machine = ToolInstaller.detect_os()
        assert system == "Darwin"
        assert machine == "arm64"

    @patch("apps.api.services.tool_installer.platform")
    def test_returns_windows_amd64(self, mock_platform):
        mock_platform.system.return_value = "Windows"
        mock_platform.machine.return_value = "AMD64"
        system, machine = ToolInstaller.detect_os()
        assert system == "Windows"
        assert machine == "AMD64"


class TestPlatformMap:
    """Tests for PLATFORM_MAP coverage."""

    def test_all_supported_platforms_present(self):
        expected_keys = [
            ("Linux", "x86_64"),
            ("Darwin", "x86_64"),
            ("Darwin", "arm64"),
            ("Windows", "AMD64"),
        ]
        for key in expected_keys:
            assert key in ToolInstaller.PLATFORM_MAP, f"Missing platform: {key}"

    def test_linux_binary_name(self):
        assert ToolInstaller.PLATFORM_MAP[("Linux", "x86_64")] == "vina_1.2.5_linux_x86_64"

    def test_darwin_x86_binary_name(self):
        assert ToolInstaller.PLATFORM_MAP[("Darwin", "x86_64")] == "vina_1.2.5_mac_x86_64"

    def test_darwin_arm64_binary_name(self):
        assert ToolInstaller.PLATFORM_MAP[("Darwin", "arm64")] == "vina_1.2.5_mac_arm64"

    def test_windows_binary_name(self):
        assert ToolInstaller.PLATFORM_MAP[("Windows", "AMD64")] == "vina_1.2.5_win32.exe"


class TestGetDownloadUrl:
    """Tests for ToolInstaller.get_download_url()."""

    @patch.object(ToolInstaller, "detect_os", return_value=("Linux", "x86_64"))
    def test_linux_url(self, _mock):
        installer = ToolInstaller()
        url = installer.get_download_url("vina")
        assert "vina_1.2.5_linux_x86_64" in url
        assert url.startswith("https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/")

    @patch.object(ToolInstaller, "detect_os", return_value=("Darwin", "arm64"))
    def test_darwin_arm64_url(self, _mock):
        installer = ToolInstaller()
        url = installer.get_download_url("vina")
        assert "vina_1.2.5_mac_arm64" in url

    @patch.object(ToolInstaller, "detect_os", return_value=("Darwin", "x86_64"))
    def test_darwin_x86_url(self, _mock):
        installer = ToolInstaller()
        url = installer.get_download_url("vina")
        assert "vina_1.2.5_mac_x86_64" in url

    @patch.object(ToolInstaller, "detect_os", return_value=("Windows", "AMD64"))
    def test_windows_url(self, _mock):
        installer = ToolInstaller()
        url = installer.get_download_url("vina")
        assert "vina_1.2.5_win32.exe" in url

    @patch.object(ToolInstaller, "detect_os", return_value=("FreeBSD", "aarch64"))
    def test_unsupported_platform_raises(self, _mock):
        installer = ToolInstaller()
        with pytest.raises(ValueError, match="No Vina binary available"):
            installer.get_download_url("vina")

    def test_unsupported_tool_raises(self):
        installer = ToolInstaller()
        with pytest.raises(ValueError, match="Unsupported tool"):
            installer.get_download_url("unknown_tool")

    @patch.object(ToolInstaller, "detect_os", return_value=("Linux", "x86_64"))
    def test_url_contains_version(self, _mock):
        installer = ToolInstaller()
        url = installer.get_download_url("vina")
        assert "v1.2.5" in url


class TestCheckAvailability:
    """Tests for ToolInstaller.check_availability()."""

    def test_returns_dict_with_vina_and_fpocket(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            installer = ToolInstaller(tools_dir=tmpdir)
            result = installer.check_availability()
            assert "vina" in result
            assert "fpocket" in result
            assert isinstance(result["vina"], ToolStatus)
            assert isinstance(result["fpocket"], ToolStatus)

    def test_vina_not_detected_when_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            installer = ToolInstaller(tools_dir=tmpdir)
            with patch("shutil.which", return_value=None):
                result = installer.check_availability()
                assert result["vina"].status == "not_detected"

    @patch("shutil.which", side_effect=lambda name: "/usr/bin/vina" if name == "vina" else None)
    def test_vina_available_on_path(self, _mock):
        with tempfile.TemporaryDirectory() as tmpdir:
            installer = ToolInstaller(tools_dir=tmpdir)
            result = installer.check_availability()
            assert result["vina"].status == "available"
            assert result["vina"].path == "/usr/bin/vina"

    def test_vina_available_in_tools_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a fake vina binary in tools dir
            system = os.name
            vina_name = "vina.exe" if system == "nt" else "vina"
            vina_path = os.path.join(tmpdir, vina_name)
            with open(vina_path, "w") as f:
                f.write("#!/bin/sh\necho vina")
            os.chmod(vina_path, 0o755)

            installer = ToolInstaller(tools_dir=tmpdir)
            with patch("shutil.which", return_value=None):
                result = installer.check_availability()
                assert result["vina"].status == "available"
                assert result["vina"].path == vina_path

    def test_install_hint_present_when_not_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            installer = ToolInstaller(tools_dir=tmpdir)
            with patch("shutil.which", return_value=None):
                result = installer.check_availability()
                assert result["vina"].install_hint != ""
                assert result["fpocket"].install_hint != ""


class TestToolsDir:
    """Tests for TOOLS_DIR configuration."""

    def test_default_tools_dir(self):
        assert ToolInstaller.TOOLS_DIR == os.path.join("apps", "api", "tools", "bin")

    def test_custom_tools_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            installer = ToolInstaller(tools_dir=tmpdir)
            assert installer.tools_dir == tmpdir

    def test_tools_dir_created_on_init(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = os.path.join(tmpdir, "custom", "bin")
            installer = ToolInstaller(tools_dir=custom_dir)
            assert os.path.isdir(custom_dir)


class TestFpocketInstall:
    """Tests for fpocket installation handling."""

    def test_fpocket_already_on_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            installer = ToolInstaller(tools_dir=tmpdir)
            with patch("shutil.which", return_value="/usr/bin/fpocket"):
                result = installer._handle_fpocket_install(0.0)
                assert result.status == "already_available"
                assert result.path == "/usr/bin/fpocket"

    def test_fpocket_not_found_returns_instructions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            installer = ToolInstaller(tools_dir=tmpdir)
            with patch("shutil.which", return_value=None):
                result = installer._handle_fpocket_install(0.0)
                assert result.status == "failed"
                assert "conda install" in result.error
                assert "fpocket" in result.error
