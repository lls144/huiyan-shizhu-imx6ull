from __future__ import annotations

from pathlib import Path

from pc.gui import app, runtime


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_source_runtime_defaults_are_repository_resources() -> None:
    args = app._parser().parse_args([])

    assert args.vision_config == REPO_ROOT / "pc/config/vision.json"
    assert args.event_config == REPO_ROOT / "pc/config/events.json"
    assert args.camera_config == REPO_ROOT / "pc/config/camera.json"
    assert args.controller_config == REPO_ROOT / "pc/config/controller_windows_ethernet.json"
    assert args.session_dir == REPO_ROOT / "output/m5/sessions"


def test_frozen_runtime_paths_do_not_depend_on_current_directory(monkeypatch, tmp_path: Path) -> None:
    executable = tmp_path / "HuiyanDemo.exe"
    bundle_data = tmp_path / "_internal"
    monkeypatch.setattr(runtime.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime.sys, "_MEIPASS", str(bundle_data), raising=False)
    monkeypatch.setattr(runtime.sys, "executable", str(executable))

    assert runtime.resource_path("pc/config/camera.json") == bundle_data / "pc/config/camera.json"
    assert runtime.writable_runtime_dir() == tmp_path
    assert runtime.runtime_git_state()["distribution"] == "PyInstaller"


def test_package_spec_includes_only_windows_profile_and_required_demo_resources() -> None:
    spec = (REPO_ROOT / "HuiyanDemo.spec").read_text(encoding="utf-8")

    for resource in (
        "camera.json",
        "controller_windows_ethernet.json",
        "events.json",
        "vision.json",
        "huiyan_logo.svg",
        "huiyan_logo.ico",
    ):
        assert resource in spec
    assert "controller_ubuntu_usb_maintenance.json" not in spec
    assert "console=False" in spec
    assert "cv2_enumerate_cameras" in spec
    assert '"icuuc.dll", "icudt78.dll"' in spec


def test_demo_entry_uses_fixed_camera_runtime_profile() -> None:
    entry = (REPO_ROOT / "pc/gui/demo_entry.py").read_text(encoding="utf-8")

    assert '"--source", "camera"' in entry
    assert '"--roi-mode", "fixed_normalized"' in entry


def test_windows_build_and_shortcut_scripts_are_repository_relative() -> None:
    build = (REPO_ROOT / "tools/windows/build_demo.ps1").read_text(encoding="utf-8")
    shortcut = (REPO_ROOT / "tools/windows/create_demo_shortcut.ps1").read_text(encoding="utf-8")

    assert "$PSScriptRoot" in build
    assert "PyInstaller" in build
    assert "Remove-Item -LiteralPath" in build
    assert "Assert-ChildPath" in build
    assert "HuiyanDemo.exe" in shortcut
    assert "0x6167" in shortcut
    assert "0x73E0" in shortcut
    assert "WScript.Shell" in shortcut
