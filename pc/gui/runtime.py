"""Runtime-safe paths, identity and logging for source and frozen demos."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


LOGGER_NAME = "huiyan.demo"


def is_frozen() -> bool:
    """Return whether this process is running from a PyInstaller bundle."""

    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    """Return the directory that contains bundled, read-only application data."""

    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parents[2]


def resource_path(relative_path: str | Path) -> Path:
    """Resolve a repository-relative packaged resource in both runtimes."""

    return resource_root() / relative_path


def writable_runtime_dir() -> Path:
    """Return a writable location beside the executable when frozen."""

    if is_frozen():
        return Path(sys.executable).resolve().parent
    return resource_root()


def configure_runtime_logging() -> Path | None:
    """Best-effort bounded file logging; logging failures never stop the demo."""

    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return None
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        log_dir = writable_runtime_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_dir / "huiyan-demo.log", encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logger.addHandler(handler)
        return log_dir / "huiyan-demo.log"
    except Exception:
        logger.addHandler(logging.NullHandler())
        return None


def runtime_git_state() -> dict[str, object]:
    """Keep session reports useful in source runs without requiring Git in a bundle."""

    if is_frozen():
        return {"commit": None, "dirty": None, "distribution": "PyInstaller"}
    from pc.vision.live import _git_state

    return _git_state()
