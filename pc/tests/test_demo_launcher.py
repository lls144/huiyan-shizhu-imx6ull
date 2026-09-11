from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_windows_demo_launcher_uses_repo_relative_venv_and_camera_profile() -> None:
    content = (REPO_ROOT / "scripts/start_demo.bat").read_text(encoding="utf-8")

    assert "%~dp0.." in content
    assert ".venv\\Scripts\\python.exe" in content
    assert 'pushd "%REPO_ROOT%"' in content
    assert "-m pc.gui --source camera --roi-mode fixed_normalized" in content
    assert "C:\\Users\\" not in content
