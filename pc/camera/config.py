"""Load and validate camera settings from JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CameraConfig:
    """Runtime settings for selecting and testing one camera."""

    device_name: str
    fallback_index: int | None
    backend: str
    requested_width: int
    requested_height: int
    requested_fps: float
    fourcc: str
    warmup_frames: int
    test_duration_seconds: float
    reopen_cycles: int
    minimum_read_success_rate: float
    maximum_frame_gap_seconds: float
    device_path: str | None = None

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "CameraConfig":
        config = cls(**values)
        config.validate()
        return config

    def validate(self) -> None:
        if not self.device_name.strip() and self.fallback_index is None and not self.device_path:
            raise ValueError("device_name, fallback_index, or device_path must be provided")
        if self.fallback_index is not None and self.fallback_index < 0:
            raise ValueError("fallback_index must be non-negative")
        if self.requested_width <= 0 or self.requested_height <= 0:
            raise ValueError("requested dimensions must be positive")
        if self.requested_fps <= 0:
            raise ValueError("requested_fps must be positive")
        if len(self.fourcc) != 4:
            raise ValueError("fourcc must contain exactly four characters")
        if self.device_path is not None and not self.device_path.strip():
            raise ValueError("device_path must not be blank when provided")
        if self.warmup_frames < 0:
            raise ValueError("warmup_frames must be non-negative")
        if self.test_duration_seconds <= 0:
            raise ValueError("test_duration_seconds must be positive")
        if self.reopen_cycles <= 0:
            raise ValueError("reopen_cycles must be positive")
        if not 0 < self.minimum_read_success_rate <= 1:
            raise ValueError("minimum_read_success_rate must be in (0, 1]")
        if self.maximum_frame_gap_seconds <= 0:
            raise ValueError("maximum_frame_gap_seconds must be positive")


def load_camera_config(path: str | Path) -> CameraConfig:
    """Read UTF-8 JSON settings and return a validated configuration."""

    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as stream:
        values = json.load(stream)
    if not isinstance(values, dict):
        raise ValueError("camera config root must be a JSON object")
    return CameraConfig.from_dict(values)
