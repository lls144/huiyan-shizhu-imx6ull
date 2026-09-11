"""Configuration loading and validation for M4 object event generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EventConfig:
    """Deterministic frame-based association and occlusion parameters."""

    min_confirm_frames: int = 2
    max_missing_frames: int = 3
    occlusion_grace_frames: int = 25
    iou_threshold: float = 0.30
    center_distance_threshold: float = 80.0

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "EventConfig":
        tracking = values.get("tracking", values)
        if not isinstance(tracking, dict):
            raise ValueError("event config tracking section must be an object")
        config = cls(**tracking)
        config.validate()
        return config

    def validate(self) -> None:
        if self.min_confirm_frames <= 0:
            raise ValueError("min_confirm_frames must be positive")
        if self.max_missing_frames < 0:
            raise ValueError("max_missing_frames must be non-negative")
        if self.occlusion_grace_frames <= 0:
            raise ValueError("occlusion_grace_frames must be positive")
        if not 0 <= self.iou_threshold <= 1:
            raise ValueError("iou_threshold must be in [0, 1]")
        if self.center_distance_threshold < 0:
            raise ValueError("center_distance_threshold must be non-negative")
        if self.iou_threshold == 0 and self.center_distance_threshold == 0:
            raise ValueError("at least one spatial association threshold must be enabled")


def load_event_config(path: str | Path) -> EventConfig:
    with Path(path).open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError("event config root must be an object")
    return EventConfig.from_dict(payload)
