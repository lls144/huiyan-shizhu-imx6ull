"""Board-state diffing for presentation-only Digital Twin animations.

This module never emits Controller commands and has no knowledge of vision
objects.  It converts already-authoritative ``PipelineState`` snapshots into
idempotent visual events for the existing Digital Sorting Line.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pc.communication.state_monitor import PipelineState, QueueItem


class AnimationEventType(StrEnum):
    SPAWN = "spawn"
    STATION_TRANSITION = "station_transition"
    BRANCH_SORT = "branch_sort"


@dataclass(frozen=True)
class DigitalTwinAnimationEvent:
    """One board-derived instruction for the presentation layer only."""

    event_type: AnimationEventType
    command_id: int
    shape: str
    source_station: str | None = None
    target_station: str | None = None
    branch: str | None = None
    sequence: int | None = None


class AnimationController:
    """Translate consecutive Controller snapshots into one-shot UI events.

    The first snapshot establishes a baseline so opening the GUI never replays
    an already-running physical line.  Every later event is based exclusively
    on queue membership, station changes, and ``last_sort.sequence``.
    """

    def __init__(self) -> None:
        self._initialized = False
        self._previous_queue: tuple[QueueItem, ...] = ()
        self._previous_station = "idle"
        self._last_sort_sequence: int | None = None

    def reset(self) -> None:
        """Forget presentation history without creating an animation."""

        self._initialized = False
        self._previous_queue = ()
        self._previous_station = "idle"
        self._last_sort_sequence = None

    def update(self, pipeline: PipelineState | None) -> tuple[DigitalTwinAnimationEvent, ...]:
        """Return new visual events once, in board-state transition order."""

        if pipeline is None:
            return ()
        if not self._initialized:
            self._record(pipeline)
            self._initialized = True
            return ()

        events: list[DigitalTwinAnimationEvent] = []
        previous_ids = {item.command_id for item in self._previous_queue}
        for item in pipeline.queue:
            if item.command_id not in previous_ids:
                events.append(
                    DigitalTwinAnimationEvent(
                        AnimationEventType.SPAWN,
                        item.command_id,
                        item.shape,
                        target_station="Station1",
                    )
                )

        previous_front = self._previous_queue[0] if self._previous_queue else None
        current_front = pipeline.queue[0] if pipeline.queue else None
        if (
            previous_front is not None
            and current_front is not None
            and previous_front.command_id == current_front.command_id
            and self._previous_station != pipeline.station
            and self._previous_station != "idle"
            and pipeline.station != "idle"
        ):
            events.append(
                DigitalTwinAnimationEvent(
                    AnimationEventType.STATION_TRANSITION,
                    current_front.command_id,
                    current_front.shape,
                    source_station=self._previous_station,
                    target_station=pipeline.station,
                )
            )

        if (
            pipeline.last_sort is not None
            and pipeline.last_sort_sequence is not None
            and pipeline.last_sort_sequence != self._last_sort_sequence
            and previous_front is not None
        ):
            events.append(
                DigitalTwinAnimationEvent(
                    AnimationEventType.BRANCH_SORT,
                    previous_front.command_id,
                    previous_front.shape,
                    source_station=self._previous_station,
                    branch=pipeline.last_sort,
                    sequence=pipeline.last_sort_sequence,
                )
            )

        self._record(pipeline)
        return tuple(events)

    def _record(self, pipeline: PipelineState) -> None:
        self._previous_queue = pipeline.queue
        self._previous_station = pipeline.station
        self._last_sort_sequence = pipeline.last_sort_sequence
