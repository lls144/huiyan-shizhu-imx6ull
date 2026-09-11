"""Qt worker that owns source, M3 processing, and M4 state outside the UI thread."""

from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal, Slot

from pc.events.adapters import detections_from_analysis
from pc.events.config import EventConfig
from pc.events.models import VisionEvent
from pc.events.tracker import ObjectStateManager
from pc.communication.vision_dispatcher import VisionEventDispatcher
from pc.vision.config import VisionConfig
from pc.vision.m3_live import analyze_preprocess_modes, save_m3_comparison_evidence
from pc.vision.pipeline import MultiImageAnalysis, analyze_multiple_objects
from pc.vision.preprocess import Image

from .models import GuiSnapshot, GuiState, WorkerSummary
from .overlay import annotated_gui_frame
from .sources import CameraFrameSource, FrameSource

Analyzer = Callable[[Image, VisionConfig, object], MultiImageAnalysis]


def _timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


class LatestSnapshotBuffer:
    """Bounded one-item handoff; publishing replaces stale display frames."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest: GuiSnapshot | None = None
        self._notification_pending = False
        self.published_count = 0
        self.consumed_count = 0
        self.overwritten_count = 0

    def publish(self, snapshot: GuiSnapshot) -> bool:
        """Return true only when the UI needs one new queued notification."""

        with self._lock:
            self.published_count += 1
            if self._latest is not None:
                self.overwritten_count += 1
            self._latest = snapshot
            if self._notification_pending:
                return False
            self._notification_pending = True
            return True

    def take_latest(self) -> GuiSnapshot | None:
        with self._lock:
            snapshot = self._latest
            self._latest = None
            self._notification_pending = False
            if snapshot is not None:
                self.consumed_count += 1
            return snapshot


class EvidenceRequestBuffer:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: deque[str] = deque(maxlen=5)

    def request(self, scenario: str) -> None:
        with self._lock:
            self._requests.append(scenario)

    def take(self) -> str | None:
        with self._lock:
            return self._requests.popleft() if self._requests else None


class VisionWorker(QObject):
    snapshot_available = Signal()
    state_changed = Signal(str)
    finished = Signal(object)

    def __init__(
        self,
        source: FrameSource,
        vision_config: VisionConfig,
        event_config: EventConfig,
        buffer: LatestSnapshotBuffer,
        evidence_requests: EvidenceRequestBuffer,
        evidence_root: Path,
        expected_labels: Sequence[str],
        analyzer: Analyzer = analyze_multiple_objects,
        event_dispatcher: VisionEventDispatcher | None = None,
    ) -> None:
        super().__init__()
        self.source = source
        self.vision_config = vision_config
        self.event_config = event_config
        self.buffer = buffer
        self.evidence_requests = evidence_requests
        self.evidence_root = evidence_root
        self.expected_labels = tuple(expected_labels)
        self.analyzer = analyzer
        self.event_dispatcher = event_dispatcher

    @Slot()
    def run(self) -> None:
        started_wall = _timestamp()
        started = time.perf_counter()
        manager = ObjectStateManager(self.event_config)
        processing_times: list[float] = []
        all_events: list[VisionEvent] = []
        evidence_records: list[dict[str, str]] = []
        frames_read = 0
        frames_processed = 0
        detection_count = 0
        error_text: str | None = None
        ended_reason = "stopped"
        source_metadata: dict[str, object] = {"source_type": self.source.source_type}
        self.state_changed.emit(GuiState.STARTING.value)
        try:
            self.source.open()
            source_metadata = self.source.metadata()
            self.state_changed.emit(GuiState.RUNNING.value)
            while not QThread.currentThread().isInterruptionRequested():
                loop_started = time.perf_counter()
                frame = self.source.read()
                if frame is None:
                    ended_reason = "eof"
                    break
                frames_read += 1
                processing_started = time.perf_counter()
                analysis = self.analyzer(frame, self.vision_config, self.source.roi)
                detections = detections_from_analysis(analysis, frames_processed)
                update = manager.process_frame(frames_processed, detections)
                if self.event_dispatcher is not None:
                    for event in update.events:
                        self.event_dispatcher.submit(event)
                annotated = annotated_gui_frame(
                    frame,
                    analysis,
                    detections,
                    update.object_states,
                )
                processing_ms = (time.perf_counter() - processing_started) * 1000.0
                processing_times.append(processing_ms)
                detection_count += len(detections)
                all_events.extend(update.events)
                elapsed = time.perf_counter() - started
                snapshot = GuiSnapshot(
                    frame_index=frames_processed,
                    timestamp=_timestamp(),
                    annotated_frame=annotated,
                    detections=detections,
                    tracked_objects=update.object_states,
                    events=update.events,
                    source_type=self.source.source_type,
                    source_status="running",
                    processed_fps=(frames_processed + 1) / elapsed if elapsed > 0 else 0.0,
                    processing_ms=processing_ms,
                    roi_bounds=analysis.preprocessing.roi_bounds,
                    roi_mode=self.source.roi_mode,
                    roi_source=self.source.roi_source,
                    preprocess_method=analysis.preprocessing.preprocess_mode,
                )
                if self.buffer.publish(snapshot):
                    self.snapshot_available.emit()

                scenario = self.evidence_requests.take()
                if scenario is not None:
                    if not isinstance(self.source, CameraFrameSource):
                        raise RuntimeError("M3 real evidence capture is available only for camera source")
                    if self.source.live_camera is None or self.source.calibration is None:
                        raise RuntimeError("camera evidence requested before calibration completed")
                    analyses = analyze_preprocess_modes(
                        frame,
                        self.vision_config,
                        self.source.calibration.roi,
                    )
                    evidence_path = save_m3_comparison_evidence(
                        frame,
                        analyses,
                        scenario,
                        self.expected_labels,
                        self.source.calibration,
                        self.source.live_camera,
                        self.vision_config,
                        self.evidence_root,
                        update,
                    )
                    evidence_records.append(
                        {"timestamp": _timestamp(), "scenario": scenario, "path": str(evidence_path)}
                    )

                frames_processed += 1
                if self.source.target_fps > 0:
                    remaining = 1.0 / self.source.target_fps - (time.perf_counter() - loop_started)
                    if remaining > 0:
                        QThread.msleep(max(1, round(remaining * 1000.0)))
            if QThread.currentThread().isInterruptionRequested():
                ended_reason = "stopped"
        except Exception as error:
            error_text = f"{type(error).__name__}: {error}"
            ended_reason = "error"
            self.state_changed.emit(GuiState.ERROR.value)
        finally:
            try:
                self.source.close()
            except Exception as close_error:
                close_text = f"{type(close_error).__name__}: {close_error}"
                error_text = f"{error_text}; close failed: {close_text}" if error_text else close_text
                ended_reason = "error"
                self.state_changed.emit(GuiState.ERROR.value)
            duration = time.perf_counter() - started
            percentile = float(np.percentile(processing_times, 95)) if processing_times else 0.0
            summary = WorkerSummary(
                started_at=started_wall,
                finished_at=_timestamp(),
                duration_seconds=round(duration, 6),
                source_type=self.source.source_type,
                source_metadata=source_metadata,
                frames_read=frames_read,
                frames_processed=frames_processed,
                detection_count=detection_count,
                event_count=len(all_events),
                processing_fps=round(frames_processed / duration, 6) if duration else 0.0,
                average_processing_ms=round(float(np.mean(processing_times)), 6) if processing_times else 0.0,
                p95_processing_ms=round(percentile, 6),
                failed_reads=self.source.failed_reads,
                error=error_text,
                ended_reason=ended_reason,
                worker_clean_shutdown=error_text is None,
                events=tuple(all_events),
                final_object_states=manager.object_states(),
                evidence_records=tuple(evidence_records),
            )
            self.finished.emit(summary)
