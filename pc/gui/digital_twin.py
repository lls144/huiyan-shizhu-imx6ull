"""Static, board-driven digital sorting line for the existing Vision Console."""

from __future__ import annotations

from dataclasses import dataclass, field

import time
from collections import deque

from PySide6.QtCore import QPointF, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from pc.communication.state_monitor import PipelineState, QueueItem

from .animation_controller import (
    AnimationController,
    AnimationEventType,
    DigitalTwinAnimationEvent,
)


BIN_BY_BRANCH = {
    "Branch1": "Triangle Bin",
    "Branch2": "Circle Bin",
    "Branch3": "Rectangle Bin",
}

STATION_BY_BRANCH = {
    "Branch1": "Station1",
    "Branch2": "Station2",
    "Branch3": "Station3",
}


def bin_for_branch(branch: str | None) -> str | None:
    return BIN_BY_BRANCH.get(branch)


def station_for_branch(branch: str | None) -> str | None:
    """Return the physical station that produced a Controller branch."""

    return STATION_BY_BRANCH.get(branch)


@dataclass
class SortSequenceTracker:
    """Count each Controller ``last_sort.sequence`` once per GUI session."""

    last_sequence: int | None = None
    initialized: bool = False
    counts: dict[str, int] = field(
        default_factory=lambda: {"Branch1": 0, "Branch2": 0, "Branch3": 0}
    )

    def update(self, pipeline: PipelineState | None) -> str | None:
        if pipeline is None:
            return None
        if not self.initialized:
            self.initialized = True
            self.last_sequence = pipeline.last_sort_sequence
            return None
        if pipeline.last_sort is None or pipeline.last_sort_sequence is None:
            return None
        if pipeline.last_sort_sequence == self.last_sequence:
            return None
        self.last_sequence = pipeline.last_sort_sequence
        self.counts[pipeline.last_sort] += 1
        return pipeline.last_sort


class DigitalSortingLine(QWidget):
    """Paint board state plus transient animations derived from board diffs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("digitalSortingLine")
        self.setMinimumHeight(255)
        self._pipeline: PipelineState | None = None
        self._animation_controller = AnimationController()
        self._sequence_tracker = SortSequenceTracker()
        self._highlighted_branch: str | None = None
        self._highlight_timer = QTimer(self)
        self._highlight_timer.setSingleShot(True)
        self._highlight_timer.timeout.connect(self._clear_highlight)
        self._transient: DigitalTwinAnimationEvent | None = None
        self._animation_queue: deque[DigitalTwinAnimationEvent] = deque()
        self._transient_started = 0.0
        self._animation_timer = QTimer(self)
        self._animation_timer.setInterval(16)
        self._animation_timer.timeout.connect(self._advance_animation)

    @property
    def sorted_counts(self) -> dict[str, int]:
        return dict(self._sequence_tracker.counts)

    @property
    def highlighted_branch(self) -> str | None:
        return self._highlighted_branch

    @property
    def animation_controller(self) -> AnimationController:
        return self._animation_controller

    @property
    def transient_animation(self) -> DigitalTwinAnimationEvent | None:
        return self._transient

    def set_pipeline(self, pipeline: PipelineState | None) -> None:
        self._pipeline = pipeline
        for event in self._animation_controller.update(pipeline):
            self._start_animation(event)
        branch = self._sequence_tracker.update(pipeline)
        if branch is not None:
            self._highlighted_branch = branch
            self._highlight_timer.start(1400)
        self.update()

    def _start_animation(self, event: DigitalTwinAnimationEvent) -> None:
        """Queue one real-board transition for a short visual overlay."""

        if self._transient is not None:
            self._animation_queue.append(event)
            return
        self._begin_animation(event)

    def _begin_animation(self, event: DigitalTwinAnimationEvent) -> None:
        self._transient = event
        self._transient_started = time.monotonic()
        self._animation_timer.start()
        self.update()

    def _advance_animation(self) -> None:
        if self._transient is None:
            if self._animation_queue:
                self._begin_animation(self._animation_queue.popleft())
            else:
                self._animation_timer.stop()
            return
        if time.monotonic() - self._transient_started >= 0.65:
            self._transient = None
            if self._animation_queue:
                self._begin_animation(self._animation_queue.popleft())
            else:
                self._animation_timer.stop()
        self.update()

    def _clear_highlight(self) -> None:
        self._highlighted_branch = None
        self.update()

    @staticmethod
    def _shape_color(shape: str) -> QColor:
        return {
            "triangle": QColor("#22c55e"),
            "circle": QColor("#3b82f6"),
            "rectangle": QColor("#f59e0b"),
        }[shape]

    def _draw_shape(self, painter: QPainter, shape: str, center: QPointF, size: float) -> None:
        painter.save()
        painter.setPen(QPen(QColor("#101010"), 2))
        painter.setBrush(self._shape_color(shape))
        if shape == "triangle":
            path = QPainterPath()
            path.moveTo(center.x(), center.y() - size * 0.62)
            path.lineTo(center.x() - size * 0.58, center.y() + size * 0.52)
            path.lineTo(center.x() + size * 0.58, center.y() + size * 0.52)
            path.closeSubpath()
            painter.drawPath(path)
        elif shape == "circle":
            painter.drawEllipse(center, size * 0.48, size * 0.48)
        else:
            painter.drawRoundedRect(
                center.x() - size * 0.58,
                center.y() - size * 0.38,
                size * 1.16,
                size * 0.76,
                5,
                5,
            )
        painter.restore()

    @staticmethod
    def _station_point(station: str | None, line_right: int, stations_y: list[int]) -> QPointF | None:
        if station in {"Station1", "Station2", "Station3"}:
            return QPointF(line_right - 48, stations_y[int(station[-1]) - 1])
        return None

    def _draw_transient(
        self,
        painter: QPainter,
        event: DigitalTwinAnimationEvent,
        *,
        entry_point: QPointF,
        line_right: int,
        bins_left: int,
        stations_y: list[int],
    ) -> None:
        elapsed = min(1.0, (time.monotonic() - self._transient_started) / 0.65)
        if event.event_type is AnimationEventType.SPAWN:
            start = entry_point
            end = self._station_point(event.target_station, line_right, stations_y) or entry_point
            size = 16 + 19 * elapsed
        elif event.event_type is AnimationEventType.STATION_TRANSITION:
            start = self._station_point(event.source_station, line_right, stations_y) or entry_point
            end = self._station_point(event.target_station, line_right, stations_y) or start
            size = 35
        else:
            start = self._station_point(event.source_station, line_right, stations_y) or entry_point
            branch_index = {"Branch1": 0, "Branch2": 1, "Branch3": 2}.get(event.branch, 1)
            end = QPointF(bins_left + 38, 83 + branch_index * 63)
            size = 35 - 12 * elapsed
        point = QPointF(
            start.x() + (end.x() - start.x()) * elapsed,
            start.y() + (end.y() - start.y()) * elapsed,
        )
        self._draw_shape(painter, event.shape, point, size)

    def paintEvent(self, _event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#202020"))
        width = self.width()
        height = self.height()
        left = 16
        queue_width = max(165, int(width * 0.23))
        line_left = queue_width + 30
        line_right = int(width * 0.73)
        bins_left = line_right + 24
        stations_y = [int(height * fraction) for fraction in (0.27, 0.53, 0.79)]
        pipeline = self._pipeline

        painter.setPen(QColor("#d4d4d4"))
        painter.drawText(left, 22, "DIGITAL SORTING LINE · BOARD STATE")
        painter.setPen(QColor("#969696"))
        if pipeline is None:
            painter.drawText(left, 43, "Awaiting pipeline_state from Controller")
            painter.end()
            return

        painter.drawText(left, 43, f"FIFO {pipeline.queue_length}/{pipeline.capacity}")
        for index in range(pipeline.capacity):
            y = 58 + index * 45
            item = pipeline.queue[index] if index < len(pipeline.queue) else None
            is_front = index == 0 and item is not None
            painter.setBrush(QColor("#2a2d2e") if not is_front else QColor("#28435a"))
            painter.setPen(QPen(QColor("#3f86d9") if is_front else QColor("#424242"), 1))
            painter.drawRoundedRect(left, y, queue_width - 20, 34, 4, 4)
            if item is None:
                painter.setPen(QColor("#606060"))
                painter.drawText(left + 10, y + 22, f"{index + 1}  —")
                continue
            self._draw_shape(painter, item.shape, QPointF(left + 31, y + 17), 19)
            painter.setPen(QColor("#f0f0f0"))
            marker = "  ← FRONT" if is_front else ""
            painter.drawText(left + 50, y + 22, f"{index + 1}  {item.shape.title()}{marker}")

        painter.setPen(QPen(QColor("#6b7280"), 3))
        painter.drawLine(line_left, 57, line_left, stations_y[-1] + 25)
        painter.setPen(QColor("#969696"))
        painter.drawText(line_left - 21, 43, "ENTRY")
        for index, station_y in enumerate(stations_y, start=1):
            station = f"Station{index}"
            active = pipeline.station == station
            painter.setBrush(QColor("#244b3b") if active else QColor("#292929"))
            painter.setPen(QPen(QColor("#73c991") if active else QColor("#4a4a4a"), 2 if active else 1))
            painter.drawRoundedRect(line_left + 24, station_y - 29, line_right - line_left - 48, 58, 7, 7)
            painter.setPen(QColor("#f0f0f0"))
            label = ("Triangle Check · KEY1", "Circle Check · KEY2", "Rectangle Check · KEY3")[index - 1]
            painter.drawText(line_left + 38, station_y - 5, f"STATION {index}")
            painter.setPen(QColor("#b5b5b5"))
            painter.drawText(line_left + 38, station_y + 15, label)
            if station_for_branch(self._highlighted_branch) == station:
                painter.setPen(QColor("#f6c453"))
                painter.drawText(line_right - 112, station_y + 15, "MATCH")
            if active and pipeline.current_object is not None:
                if not (
                    self._transient is not None
                    and self._transient.command_id == pipeline.queue[0].command_id
                    and self._transient.event_type is AnimationEventType.STATION_TRANSITION
                ):
                    self._draw_shape(painter, pipeline.current_object, QPointF(line_right - 48, station_y), 35)

        painter.setPen(QColor("#d4d4d4"))
        painter.drawText(bins_left, 43, "SORT BINS")
        for index, branch in enumerate(("Branch1", "Branch2", "Branch3")):
            y = 59 + index * 63
            highlighted = branch == self._highlighted_branch
            painter.setBrush(QColor("#5b4220") if highlighted else QColor("#292929"))
            painter.setPen(QPen(QColor("#f59e0b") if highlighted else QColor("#4a4a4a"), 2 if highlighted else 1))
            painter.drawRoundedRect(bins_left, y, width - bins_left - 16, 48, 7, 7)
            painter.setPen(QColor("#f0f0f0"))
            painter.drawText(bins_left + 10, y + 21, BIN_BY_BRANCH[branch])
            painter.setPen(QColor("#969696"))
            painter.drawText(bins_left + 10, y + 39, f"MATCHES {self._sequence_tracker.counts[branch]}")
        if self._transient is not None:
            self._draw_transient(
                painter,
                self._transient,
                entry_point=QPointF(line_left, 58),
                line_right=line_right,
                bins_left=bins_left,
                stations_y=stations_y,
            )
        painter.end()
