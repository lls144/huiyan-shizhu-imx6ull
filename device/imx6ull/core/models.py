"""Immutable controller-domain values shared by FIFO, FSM and TCP adapter."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

SHAPES = frozenset({"triangle", "circle", "rectangle"})


@dataclass(frozen=True)
class Command:
    command_id: int
    shape: str
    source_event_id: int | None = None
    source_object_id: int | None = None

    def __post_init__(self) -> None:
        if type(self.command_id) is not int or self.command_id <= 0:
            raise ValueError("command_id must be a positive integer")
        if self.shape not in SHAPES:
            raise ValueError("shape must be triangle, circle, or rectangle")
        for field in ("source_event_id", "source_object_id"):
            value = getattr(self, field)
            if value is not None and (type(value) is not int or value <= 0):
                raise ValueError(f"{field} must be a positive integer when supplied")

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


class Key(StrEnum):
    KEY1 = "KEY1"
    KEY2 = "KEY2"
    KEY3 = "KEY3"


class TransitionKind(StrEnum):
    MOVED = "MOVED"
    SORTED = "SORTED"
    WRONG_STATION = "WRONG_STATION"
    EMPTY = "EMPTY"


@dataclass(frozen=True)
class PipelineTransition:
    kind: TransitionKind
    station: str
    command: Command | None = None
    branch: str | None = None


@dataclass(frozen=True)
class CoreResult:
    status: str
    pipeline_state: dict[str, Any]
    command: Command | None = None
    branch: str | None = None
