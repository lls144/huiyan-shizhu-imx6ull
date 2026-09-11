"""Presentation-only PySide6 main window consuming synchronized snapshots."""

from __future__ import annotations

import json
import platform
from collections import deque
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Sequence

import cv2
import PySide6
from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtGui import QColor, QCloseEvent, QImage, QKeyEvent, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pc.events.config import EventConfig
from pc.vision.config import VisionConfig
from pc.vision.live import _git_state
from pc.communication.state_monitor import BoardMonitorSnapshot, BoardStateMonitor, ConnectionStatus
from pc.communication.vision_dispatcher import EnqueueResult, VisionEventDispatcher

from .models import GuiSnapshot, GuiState, WorkerSummary
from .digital_twin import DigitalSortingLine
from .sources import FrameSource
from .theme import APP_STYLE, THEME, load_ui_fonts
from .worker import Analyzer, EvidenceRequestBuffer, LatestSnapshotBuffer, VisionWorker

SourceFactory = Callable[[], FrameSource]


def bgr_to_qimage(frame: object) -> QImage:
    """Return an owning RGB QImage so NumPy storage may be released safely."""

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  # type: ignore[arg-type]
    height, width, channels = rgb.shape
    return QImage(rgb.data, width, height, channels * width, QImage.Format.Format_RGB888).copy()


def _divider() -> QFrame:
    line = QFrame()
    line.setObjectName("divider")
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    return line


def _section(title: str, content: QWidget) -> QWidget:
    section = QWidget()
    layout = QVBoxLayout(section)
    layout.setContentsMargins(12, 8, 10, 6)
    layout.setSpacing(4)
    heading = QLabel(title.upper())
    heading.setObjectName("sectionTitle")
    layout.addWidget(heading)
    layout.addWidget(content, 1)
    return section


def _tool_button(text: str, object_name: str = "") -> QToolButton:
    button = QToolButton()
    button.setText(text)
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
    if object_name:
        button.setObjectName(object_name)
    return button


def _set_dynamic_property(widget: QWidget, name: str, value: object) -> None:
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class MainWindow(QMainWindow):
    def __init__(
        self,
        source_factory: SourceFactory,
        source_type: str,
        vision_config: VisionConfig,
        event_config: EventConfig,
        session_dir: Path,
        evidence_root: Path,
        expected_labels: Sequence[str],
        analyzer: Analyzer,
        board_monitor: BoardStateMonitor | None = None,
        event_dispatcher: VisionEventDispatcher | None = None,
    ) -> None:
        super().__init__()
        load_ui_fonts()
        self.source_factory = source_factory
        self.source_type = source_type
        self.vision_config = vision_config
        self.event_config = event_config
        self.session_dir = session_dir
        self.evidence_root = evidence_root
        self.expected_labels = tuple(expected_labels)
        self.analyzer = analyzer
        self._board_monitor = board_monitor
        self._event_dispatcher = event_dispatcher
        self._board_timer: QTimer | None = None
        self._thread: QThread | None = None
        self._worker: VisionWorker | None = None
        self._buffer: LatestSnapshotBuffer | None = None
        self._requests: EvidenceRequestBuffer | None = None
        self._last_image: QImage | None = None
        self._last_frame_index = -1
        self._last_snapshot: GuiSnapshot | None = None
        self._gui_updates = 0
        self._recent_events: deque[tuple[str, str]] = deque(maxlen=30)
        self._enqueue_records: list[dict[str, object]] = []
        self._state = GuiState.IDLE
        self.last_session_summary: dict[str, object] | None = None
        self.session_annotations: dict[str, object] = {}
        self._build_ui()
        self.setStyleSheet(APP_STYLE)
        self.setWindowTitle("慧眼识珠 · Vision Console")
        self.setMinimumSize(960, 600)
        self.resize(1366, 768)
        self._set_state(GuiState.IDLE)
        self._start_board_monitor()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_application_bar())

        self.workspace_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.workspace_splitter.setChildrenCollapsible(False)
        self.workspace_splitter.addWidget(self._build_workspace())
        self.workspace_splitter.addWidget(self._build_inspector())
        self.workspace_splitter.setStretchFactor(0, 1)
        self.workspace_splitter.setStretchFactor(1, 0)
        self.workspace_splitter.setSizes([1000, 366])
        outer.addWidget(self.workspace_splitter, 1)
        self.setCentralWidget(root)
        self._build_status_bar()

    def _build_application_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("applicationBar")
        bar.setFixedHeight(THEME.app_bar_height)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)
        title = QLabel("慧眼识珠")
        title.setObjectName("appTitle")
        subtitle = QLabel("AI VISUAL WAREHOUSE")
        subtitle.setObjectName("appSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch()
        self.state_dot = QLabel("●")
        self.state_dot.setObjectName("stateDot")
        self.state_text = QLabel("Idle")
        self.state_text.setObjectName("stateText")
        self.state_chip = self.state_text
        layout.addWidget(self.state_dot)
        layout.addWidget(self.state_text)
        return bar

    def _build_workspace(self) -> QFrame:
        workspace = QFrame()
        workspace.setObjectName("workspace")
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QFrame()
        toolbar.setObjectName("workspaceToolbar")
        toolbar.setFixedHeight(THEME.workspace_bar_height)
        tools = QHBoxLayout(toolbar)
        tools.setContentsMargins(10, 0, 8, 0)
        tools.setSpacing(5)
        heading = QLabel("VISION")
        heading.setObjectName("workspaceTitle")
        self.source_badge = QLabel(self.source_type.upper())
        self.source_badge.setObjectName("sourceBadge")
        tools.addWidget(heading)
        tools.addWidget(self.source_badge)
        tools.addStretch()
        self.start_button = _tool_button("Start", "startTool")
        self.stop_button = _tool_button("Stop")
        self.start_button.clicked.connect(self.start_session)
        self.stop_button.clicked.connect(self.stop_session)
        tools.addWidget(self.start_button)
        tools.addWidget(self.stop_button)
        layout.addWidget(toolbar)

        self.video_label = QLabel("No video source\nSelect Start to begin")
        self.video_label.setObjectName("video")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(480, 300)
        self.video_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.digital_twin = DigitalSortingLine()
        live_splitter = QSplitter(Qt.Orientation.Vertical)
        live_splitter.setChildrenCollapsible(False)
        live_splitter.addWidget(self.video_label)
        live_splitter.addWidget(self.digital_twin)
        live_splitter.setStretchFactor(0, 3)
        live_splitter.setStretchFactor(1, 2)
        live_splitter.setSizes([420, 280])
        layout.addWidget(live_splitter, 1)

        evidence = QFrame()
        evidence.setObjectName("evidenceToolbar")
        evidence.setFixedHeight(THEME.evidence_bar_height)
        evidence_layout = QHBoxLayout(evidence)
        evidence_layout.setContentsMargins(10, 0, 8, 0)
        evidence_layout.setSpacing(2)
        label = QLabel("EVIDENCE")
        label.setObjectName("sectionTitle")
        evidence_layout.addWidget(label)
        evidence_layout.addSpacing(5)
        self.scenario_buttons: list[QToolButton] = []
        for key, text, scenario in (
            ("1", "Normal", "normal_light"),
            ("2", "Bright", "bright_or_side_light"),
            ("3", "Dark", "dark_light"),
            ("4", "Occlusion", "partial_occlusion"),
            ("5", "Touching", "touching_or_merged"),
        ):
            button = _tool_button(f"{key}  {text}", "evidenceTool")
            button.clicked.connect(lambda checked=False, value=scenario: self.request_evidence(value))
            self.scenario_buttons.append(button)
            evidence_layout.addWidget(button)
        evidence_layout.addStretch()
        layout.addWidget(evidence)
        return workspace

    def _build_inspector(self) -> QFrame:
        inspector = QFrame()
        inspector.setObjectName("inspector")
        inspector.setMinimumWidth(THEME.sidebar_min_width)
        inspector.setMaximumWidth(THEME.sidebar_max_width)
        layout = QVBoxLayout(inspector)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(THEME.workspace_bar_height)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 0, 10, 0)
        title = QLabel("INSPECTOR")
        title.setObjectName("inspectorTitle")
        header_layout.addWidget(title)
        header_layout.addStretch()
        layout.addWidget(header)
        layout.addWidget(_divider())

        board = QWidget()
        board_grid = QGridLayout(board)
        board_grid.setContentsMargins(0, 0, 0, 0)
        board_grid.setHorizontalSpacing(10)
        board_grid.setVerticalSpacing(4)
        self.camera_connection_value = self._board_value("OFFLINE")
        self.board_connection_value = self._board_value("CONNECTING")
        self.controller_connection_value = self._board_value("CONNECTING")
        self.fifo_value = self._board_value("—/3")
        self.station_value = self._board_value("—")
        self.current_object_value = self._board_value("—")
        self.last_key_value = self._board_value("—")
        self.last_sort_value = self._board_value("—")
        self.last_enqueue_value = self._board_value("—")
        rows = (
            ("CAMERA", self.camera_connection_value),
            ("BOARD", self.board_connection_value),
            ("CONTROLLER", self.controller_connection_value),
            ("FIFO", self.fifo_value),
            ("STATION", self.station_value),
            ("CURRENT OBJECT", self.current_object_value),
            ("LAST KEY", self.last_key_value),
            ("LAST SORT", self.last_sort_value),
            ("LAST ENQUEUE", self.last_enqueue_value),
        )
        for row, (key_text, value) in enumerate(rows):
            key = QLabel(key_text)
            key.setObjectName("metadataKey")
            board_grid.addWidget(key, row, 0)
            board_grid.addWidget(value, row, 1)
        layout.addWidget(_section("Board state", board))
        layout.addWidget(_divider())

        session = QWidget()
        grid = QGridLayout(session)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)
        self.roi_bounds_value = QLabel("—")
        self.roi_bounds_value.setObjectName("metadataValue")
        self.error_value = QLabel("No errors")
        self.error_value.setObjectName("errorValue")
        self.error_value.setWordWrap(True)
        for row, (key_text, value) in enumerate(
            (("ROI bounds", self.roi_bounds_value), ("Last error", self.error_value))
        ):
            key = QLabel(key_text)
            key.setObjectName("metadataKey")
            grid.addWidget(key, row, 0)
            grid.addWidget(value, row, 1)
        layout.addWidget(_section("Session", session))
        layout.addWidget(_divider())

        self.detection_list = QListWidget()
        layout.addWidget(_section("Detections", self.detection_list), 1)
        layout.addWidget(_divider())
        self.object_list = QListWidget()
        layout.addWidget(_section("Tracked objects", self.object_list), 1)
        layout.addWidget(_divider())
        self.event_list = QListWidget()
        layout.addWidget(_section("Events", self.event_list), 1)
        return inspector

    @staticmethod
    def _board_value(text: str) -> QLabel:
        value = QLabel(text)
        value.setObjectName("boardStateValue")
        return value

    def _build_status_bar(self) -> None:
        bar = QStatusBar()
        bar.setObjectName("statusBar")
        bar.setSizeGripEnabled(False)
        self.setStatusBar(bar)
        self.status_source = QLabel("SOURCE —")
        self.status_fps = QLabel("— FPS")
        self.status_latency = QLabel("— ms")
        self.status_frame = QLabel("FRAME —")
        self.status_roi = QLabel("ROI —")
        self.status_preprocess = QLabel("PIPELINE —")
        self.status_state = QLabel("IDLE")
        self.status_camera_connection = QLabel("CAMERA OFFLINE")
        self.status_board_connection = QLabel("BOARD CONNECTING")
        self.status_source.setObjectName("statusSource")
        self.status_state.setObjectName("statusState")
        for widget in (
            self.status_fps,
            self.status_latency,
            self.status_frame,
            self.status_roi,
            self.status_preprocess,
        ):
            widget.setObjectName("statusItem")
        for widget in (
            self.status_source,
            self.status_fps,
            self.status_latency,
            self.status_frame,
            self.status_roi,
            self.status_preprocess,
        ):
            bar.addWidget(widget)
        bar.addPermanentWidget(self.status_camera_connection)
        bar.addPermanentWidget(self.status_board_connection)
        bar.addPermanentWidget(self.status_state)
        self.metrics: dict[str, QLabel] = {
            "source": self.status_source,
            "fps": self.status_fps,
            "latency": self.status_latency,
            "frame": self.status_frame,
            "roi": self.status_roi,
            "preprocess": self.status_preprocess,
            "error": self.error_value,
        }

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    @property
    def state(self) -> GuiState:
        return self._state

    @property
    def last_snapshot(self) -> GuiSnapshot | None:
        return self._last_snapshot

    def _set_state(self, state: GuiState) -> None:
        self._state = state
        display = state.value.title()
        self.state_text.setText(display)
        self.status_state.setText(state.value.upper())
        _set_dynamic_property(self.state_dot, "state", state.value)
        active = state in {GuiState.STARTING, GuiState.RUNNING, GuiState.STOPPING}
        self.start_button.setEnabled(not active)
        self.stop_button.setEnabled(state in {GuiState.STARTING, GuiState.RUNNING})
        camera_running = self.source_type == "camera" and state == GuiState.RUNNING
        for button in self.scenario_buttons:
            button.setEnabled(camera_running)
        self._set_camera_connection("ONLINE" if camera_running else "OFFLINE")

    def _start_board_monitor(self) -> None:
        if self._board_monitor is None:
            self._apply_board_snapshot(
                BoardMonitorSnapshot(ConnectionStatus.OFFLINE, None, "Board monitor is not configured")
            )
            return
        self._apply_board_snapshot(self._board_monitor.start())
        self._board_timer = QTimer(self)
        self._board_timer.setInterval(50)
        self._board_timer.timeout.connect(self._poll_board_monitor)
        self._board_timer.start()

    def _poll_board_monitor(self) -> None:
        if self._board_monitor is None:
            return
        snapshot = self._board_monitor.poll()
        if snapshot is not None:
            self._apply_board_snapshot(snapshot)
        self._drain_enqueue_results()

    def _set_camera_connection(self, status: str) -> None:
        self.camera_connection_value.setText(status)
        self.status_camera_connection.setText(f"CAMERA {status}")
        _set_dynamic_property(self.camera_connection_value, "connection", status.lower())

    def _apply_board_snapshot(self, snapshot: BoardMonitorSnapshot) -> None:
        connection = snapshot.connection.value.upper()
        self.board_connection_value.setText(connection)
        self.controller_connection_value.setText(connection)
        self.status_board_connection.setText(f"BOARD {connection}")
        for value in (self.board_connection_value, self.controller_connection_value):
            _set_dynamic_property(value, "connection", snapshot.connection.value)
        pipeline = snapshot.pipeline
        if pipeline is None:
            self.fifo_value.setText("—/3")
            self.station_value.setText("—")
            self.current_object_value.setText("—")
            self.last_key_value.setText("—")
            self.last_sort_value.setText("—")
        else:
            self.fifo_value.setText(f"{pipeline.queue_length}/{pipeline.capacity}")
            self.station_value.setText(pipeline.display_station)
            self.current_object_value.setText((pipeline.current_object or "none").upper())
            self.last_key_value.setText(pipeline.last_key or "none")
            self.last_sort_value.setText(pipeline.last_sort or "none")
        self.digital_twin.set_pipeline(pipeline)
        if snapshot.error:
            self.statusBar().showMessage(f"Board monitor: {snapshot.error}", 3000)

    def _drain_enqueue_results(self) -> None:
        if self._event_dispatcher is None:
            return
        for result in self._event_dispatcher.drain():
            self._apply_enqueue_result(result)

    def _apply_enqueue_result(self, result: EnqueueResult) -> None:
        record = result.to_record()
        self._enqueue_records.append(record)
        command = f" · cmd {result.command_id}" if result.command_id is not None else ""
        self.last_enqueue_value.setText(f"{result.outcome.upper()} · {result.shape}{command}")
        _set_dynamic_property(
            self.last_enqueue_value,
            "enqueueOutcome",
            "accepted" if result.outcome == "accepted" else "failed",
        )
        self.statusBar().showMessage(
            f"Vision event #{result.event_id} · {result.outcome}: {result.message}",
            5000,
        )

    def start_session(self) -> None:
        if self.is_running:
            return
        self._last_frame_index = -1
        self._gui_updates = 0
        self._recent_events.clear()
        self.event_list.clear()
        self.error_value.setText("No errors")
        _set_dynamic_property(self.error_value, "hasError", False)
        self._buffer = LatestSnapshotBuffer()
        self._requests = EvidenceRequestBuffer()
        source = self.source_factory()
        thread = QThread(self)
        worker = VisionWorker(
            source,
            self.vision_config,
            self.event_config,
            self._buffer,
            self._requests,
            self.evidence_root,
            self.expected_labels,
            self.analyzer,
            self._event_dispatcher,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.snapshot_available.connect(self._consume_latest)
        worker.state_changed.connect(self._on_worker_state)
        worker.finished.connect(self._on_worker_summary)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        self._thread = thread
        self._worker = worker
        self._set_state(GuiState.STARTING)
        thread.start()

    def stop_session(self, block: bool = False) -> None:
        if self._thread is None or not self._thread.isRunning():
            return
        self._set_state(GuiState.STOPPING)
        self._thread.requestInterruption()
        if block:
            self._thread.wait(5000)
            QApplication.processEvents()

    def request_evidence(self, scenario: str) -> None:
        if self.source_type != "camera" or self._requests is None or not self.is_running:
            return
        self._requests.request(scenario)
        self.statusBar().showMessage(f"Evidence queued · {scenario.replace('_', ' ').title()}", 2500)

    def _on_worker_state(self, value: str) -> None:
        self._set_state(GuiState(value))

    @staticmethod
    def _add_muted_item(widget: QListWidget, text: str) -> None:
        item = QListWidgetItem(text)
        item.setForeground(QColor(THEME.muted_text))
        widget.addItem(item)

    def _consume_latest(self) -> None:
        if self._buffer is None:
            return
        snapshot = self._buffer.take_latest()
        if snapshot is None or snapshot.frame_index <= self._last_frame_index:
            return
        self._last_frame_index = snapshot.frame_index
        self._last_snapshot = snapshot
        self._gui_updates += 1
        self._last_image = bgr_to_qimage(snapshot.annotated_frame)
        self._render_image()

        self.status_source.setText(snapshot.source_type.upper())
        self.status_fps.setText(f"{snapshot.processed_fps:.1f} FPS")
        self.status_latency.setText(f"{snapshot.processing_ms:.2f} ms")
        self.status_frame.setText(f"FRAME {snapshot.frame_index}")
        self.status_roi.setText(f"ROI {snapshot.roi_mode.replace('_normalized', '').upper()}")
        self.status_preprocess.setText(snapshot.preprocess_method.upper())
        bounds = ", ".join(str(value) for value in snapshot.roi_bounds)
        self.roi_bounds_value.setText(f"[{bounds}]")

        self.detection_list.clear()
        for detection in snapshot.detections:
            self.detection_list.addItem(
                f"{detection.label.title():<20}{detection.confidence * 100:>6.1f}%"
            )
        if not snapshot.detections:
            self._add_muted_item(self.detection_list, "No detections")

        self.object_list.clear()
        for state in snapshot.tracked_objects:
            if state.active:
                self.object_list.addItem(
                    f"#{state.object_id:<3}{state.label.title():<15}{state.status.upper():>10}"
                )
        if self.object_list.count() == 0:
            self._add_muted_item(self.object_list, "No tracked objects")

        event_time = snapshot.timestamp[11:19] if len(snapshot.timestamp) >= 19 else "--:--:--"
        for event in snapshot.events:
            kind = event.event_type.value.removeprefix("OBJECT_")
            self._recent_events.appendleft(
                (f"{event_time}  {kind:<5}  #{event.object_id:<3}{event.label}", kind)
            )
        self.event_list.clear()
        for text, kind in self._recent_events:
            item = QListWidgetItem(text)
            item.setForeground(QColor(THEME.success if kind == "ENTER" else THEME.warning))
            self.event_list.addItem(item)
        if not self._recent_events:
            self._add_muted_item(self.event_list, "No events")

    def _render_image(self) -> None:
        if self._last_image is None:
            return
        pixmap = QPixmap.fromImage(self._last_image).scaled(
            self.video_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video_label.setPixmap(pixmap)

    def _on_worker_summary(self, summary: WorkerSummary) -> None:
        record = summary.to_record()
        record.update(
            {
                "schema_version": 1,
                "milestone": "M5",
                "acceptance_status": "synthetic_offline_observation"
                if summary.source_type == "synthetic"
                else "pending_user_validation",
                "git": _git_state(),
                "environment": {
                    "platform": platform.platform(),
                    "python": platform.python_version(),
                    "pyside6": PySide6.__version__,
                },
                "vision_config": asdict(self.vision_config),
                "event_config": asdict(self.event_config),
                "gui_updates": self._gui_updates,
                "gui_update_fps": round(self._gui_updates / summary.duration_seconds, 6)
                if summary.duration_seconds
                else 0.0,
                "display_frames_dropped": max(0, summary.frames_processed - self._gui_updates),
                "buffer_overwrites": self._buffer.overwritten_count if self._buffer else 0,
                "clean_shutdown": summary.worker_clean_shutdown,
                "controller_enqueues": list(self._enqueue_records),
                **self.session_annotations,
            }
        )
        self.last_session_summary = record
        self.session_dir.mkdir(parents=True, exist_ok=True)
        safe_timestamp = summary.started_at.replace(":", "").replace("+", "_")
        path = self.session_dir / f"session-{safe_timestamp}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if summary.error:
            self.error_value.setText(summary.error)
            _set_dynamic_property(self.error_value, "hasError", True)
            if self._last_image is None:
                self.video_label.setText("Source unavailable\nSee Last error in Inspector")
            self._set_state(GuiState.ERROR)

    def _on_thread_finished(self) -> None:
        had_error = self._state == GuiState.ERROR
        self._thread = None
        self._worker = None
        self._requests = None
        if not had_error:
            self._set_state(GuiState.IDLE)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._render_image()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        mapping = {
            Qt.Key.Key_1: "normal_light",
            Qt.Key.Key_2: "bright_or_side_light",
            Qt.Key.Key_3: "dark_light",
            Qt.Key.Key_4: "partial_occlusion",
            Qt.Key.Key_5: "touching_or_merged",
        }
        if event.key() in mapping:
            self.request_evidence(mapping[event.key()])
            return
        super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.is_running:
            self.stop_session(block=True)
        if self.is_running:
            self.error_value.setText("Worker did not stop within 5 seconds")
            _set_dynamic_property(self.error_value, "hasError", True)
            event.ignore()
            return
        if self._board_timer is not None:
            self._board_timer.stop()
        if self._event_dispatcher is not None:
            self._event_dispatcher.close()
        if self._board_monitor is not None:
            self._board_monitor.close()
        event.accept()
