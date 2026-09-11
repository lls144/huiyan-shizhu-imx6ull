import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np
import pytest
from PySide6.QtCore import QEventLoop
from PySide6.QtWidgets import QApplication, QFrame

from pc.events.config import EventConfig, load_event_config
from pc.gui.models import GuiState
from pc.gui.sources import SyntheticFrameSource
from pc.gui.window import MainWindow, bgr_to_qimage
from pc.vision.config import VisionConfig, load_vision_config
from pc.vision.pipeline import analyze_multiple_objects
from pc.vision.roi import NormalizedRoi, fixed_roi

REPO_ROOT = Path(__file__).resolve().parents[2]
VISION_CONFIG = load_vision_config(REPO_ROOT / "pc/config/vision.json")
EVENT_CONFIG = load_event_config(REPO_ROOT / "pc/config/events.json")
NORMAL_IMAGE = cv2.imread(
    str(REPO_ROOT / "test_data/m3/synthetic/multi_normal.png"), cv2.IMREAD_COLOR
)
assert NORMAL_IMAGE is not None


@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    return QApplication.instance() or QApplication(["pytest-m5"])


def _wait_until(qt_app: QApplication, predicate: Callable[[], bool], timeout_ms: int = 4000) -> None:
    deadline = time.perf_counter() + timeout_ms / 1000
    while time.perf_counter() < deadline:
        qt_app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 10)
        if predicate():
            return
    raise AssertionError("condition was not reached before bounded GUI timeout")


class SequenceSource:
    source_type = "synthetic"
    target_fps = 100.0
    roi_mode = "fixed_normalized"
    roi_source = "configured"

    def __init__(
        self,
        frames: list[np.ndarray],
        vision_config: VisionConfig = VISION_CONFIG,
        loop: bool = False,
    ) -> None:
        self.frames = frames
        self.roi: NormalizedRoi = fixed_roi(vision_config)
        self.loop = loop
        self.failed_reads = 0
        self.index = 0
        self.opened = False

    def open(self) -> None:
        self.index = 0
        self.opened = True

    def read(self) -> np.ndarray | None:
        if not self.opened:
            raise RuntimeError("not open")
        if self.index >= len(self.frames):
            if not self.loop:
                return None
            self.index = 0
        frame = self.frames[self.index]
        self.index += 1
        return frame

    def close(self) -> None:
        self.opened = False

    def metadata(self) -> dict[str, Any]:
        return {"source_type": self.source_type, "frame_count": len(self.frames)}


class OpenFailureSource(SequenceSource):
    def open(self) -> None:
        raise RuntimeError("intentional open failure")


class ReadFailureSource(SequenceSource):
    def read(self) -> np.ndarray | None:
        raise RuntimeError("intentional read failure")


def _window(tmp_path: Path, source_factory: Callable[[], Any], analyzer=analyze_multiple_objects) -> MainWindow:
    window = MainWindow(
        source_factory=source_factory,
        source_type="synthetic",
        vision_config=VISION_CONFIG,
        event_config=EVENT_CONFIG,
        session_dir=tmp_path / "sessions",
        evidence_root=tmp_path / "evidence",
        expected_labels=("triangle", "rectangle", "circle"),
        analyzer=analyzer,
    )
    window.show()
    return window


def test_qimage_owns_data_after_numpy_frame_changes() -> None:
    frame = np.zeros((10, 20, 3), dtype=np.uint8)
    image = bgr_to_qimage(frame)
    frame[:] = 255

    assert image.width() == 20
    assert image.height() == 10
    assert image.pixelColor(0, 0).red() == 0


def test_desktop_workspace_hierarchy_is_compact(qt_app: QApplication, tmp_path: Path) -> None:
    window = _window(tmp_path, lambda: SequenceSource([NORMAL_IMAGE]))
    window.resize(1366, 768)
    qt_app.processEvents()

    assert window.findChild(QFrame, "applicationBar").height() == 40
    assert window.findChild(QFrame, "inspector").width() >= 300
    assert window.workspace_splitter.count() == 2
    assert window.workspace_splitter.sizes()[0] > window.workspace_splitter.sizes()[1] * 2
    assert window.statusBar().height() <= 26
    assert window.start_button.height() <= 30
    assert window.stop_button.height() <= 30
    assert not window.findChildren(QFrame, "card")
    assert window.camera_connection_value.text() == "OFFLINE"
    assert window.board_connection_value.text() == "OFFLINE"
    assert window.controller_connection_value.text() == "OFFLINE"
    assert window.fifo_value.text() == "—/3"

    window.resize(1920, 1080)
    qt_app.processEvents()
    assert window.findChild(QFrame, "inspector").width() <= 420
    assert window.statusBar().height() <= 26
    window.close()


def test_window_displays_synchronized_m3_m4_snapshot_and_resize(
    qt_app: QApplication, tmp_path: Path
) -> None:
    direct = analyze_multiple_objects(NORMAL_IMAGE, VISION_CONFIG, fixed_roi(VISION_CONFIG))
    window = _window(tmp_path, lambda: SequenceSource([NORMAL_IMAGE, NORMAL_IMAGE]))
    window.start_session()
    _wait_until(qt_app, lambda: window.last_session_summary is not None and not window.is_running)

    snapshot = window.last_snapshot
    assert snapshot is not None
    assert [item.label for item in snapshot.detections] == ["triangle", "rectangle", "circle"]
    assert [item.confidence for item in snapshot.detections] == [
        item.confidence for item in direct.detections
    ]
    assert all(item.frame_index == snapshot.frame_index for item in snapshot.detections)
    assert {item.label for item in snapshot.tracked_objects if item.confirmed} == {
        "triangle",
        "rectangle",
        "circle",
    }
    assert [item.label for item in snapshot.events] == ["triangle", "rectangle", "circle"]
    assert window.detection_list.count() == 3
    assert window.object_list.count() == 3
    assert window.event_list.count() == 3
    assert window.video_label.pixmap() is not None

    window.resize(1000, 650)
    qt_app.processEvents()
    pixmap = window.video_label.pixmap()
    assert pixmap is not None
    assert pixmap.width() <= window.video_label.width()
    assert pixmap.height() <= window.video_label.height()
    window.close()


def test_full_synthetic_lifecycle_has_one_enter_and_exit_per_object(
    qt_app: QApplication, tmp_path: Path
) -> None:
    blank = np.full_like(NORMAL_IMAGE, 245)
    frames = [blank] * 2 + [NORMAL_IMAGE] * 3 + [blank] * 4
    window = _window(tmp_path, lambda: SequenceSource(frames))
    window.start_session()
    _wait_until(qt_app, lambda: window.last_session_summary is not None and not window.is_running)

    record = window.last_session_summary
    assert record is not None
    events = record["events"]
    assert [(item["event_type"], item["label"]) for item in events] == [
        (kind, label)
        for kind in ("OBJECT_ENTER", "OBJECT_EXIT")
        for label in ("triangle", "rectangle", "circle")
    ]
    assert record["error"] is None
    assert record["clean_shutdown"] is True
    assert list((tmp_path / "sessions").glob("session-*.json"))
    window.close()


def test_start_stop_restart_has_no_orphan_worker(qt_app: QApplication, tmp_path: Path) -> None:
    window = _window(tmp_path, lambda: SequenceSource([NORMAL_IMAGE], loop=True))
    window.start_session()
    _wait_until(qt_app, lambda: window.state == GuiState.RUNNING)
    window.stop_session(block=True)
    _wait_until(qt_app, lambda: not window.is_running)
    first = window.last_session_summary

    window.start_session()
    _wait_until(qt_app, lambda: window.state == GuiState.RUNNING)
    window.stop_session(block=True)
    _wait_until(qt_app, lambda: not window.is_running and window.last_session_summary is not first)

    assert window.state == GuiState.IDLE
    assert window.last_session_summary["clean_shutdown"] is True  # type: ignore[index]
    window.close()


@pytest.mark.parametrize(
    ("source_factory", "error_fragment"),
    [
        (lambda: OpenFailureSource([NORMAL_IMAGE]), "intentional open failure"),
        (lambda: ReadFailureSource([NORMAL_IMAGE]), "intentional read failure"),
    ],
)
def test_source_failures_are_visible_and_recoverable(
    qt_app: QApplication,
    tmp_path: Path,
    source_factory: Callable[[], Any],
    error_fragment: str,
) -> None:
    attempts = 0

    def retrying_factory() -> Any:
        nonlocal attempts
        attempts += 1
        return source_factory() if attempts == 1 else SequenceSource([NORMAL_IMAGE, NORMAL_IMAGE])

    window = _window(tmp_path, retrying_factory)
    window.start_session()
    _wait_until(qt_app, lambda: window.state == GuiState.ERROR and not window.is_running)
    assert error_fragment in window.metrics["error"].text()
    assert window.last_session_summary["ended_reason"] == "error"  # type: ignore[index]

    window.start_session()
    _wait_until(qt_app, lambda: attempts == 2 and window.state == GuiState.IDLE)
    assert window.last_session_summary["error"] is None  # type: ignore[index]
    assert window.state == GuiState.IDLE
    window.close()


def test_vision_failure_is_reported_without_crashing_ui(
    qt_app: QApplication, tmp_path: Path
) -> None:
    def failing_analyzer(image: np.ndarray, config: VisionConfig, roi: object) -> Any:
        raise ValueError("intentional vision failure")

    window = _window(tmp_path, lambda: SequenceSource([NORMAL_IMAGE]), failing_analyzer)
    window.start_session()
    _wait_until(qt_app, lambda: window.state == GuiState.ERROR and not window.is_running)

    assert "intentional vision failure" in window.metrics["error"].text()
    assert window.last_session_summary["clean_shutdown"] is False  # type: ignore[index]
    window.close()


def test_close_while_running_stops_worker(qt_app: QApplication, tmp_path: Path) -> None:
    window = _window(tmp_path, lambda: SequenceSource([NORMAL_IMAGE], loop=True))
    window.start_session()
    _wait_until(qt_app, lambda: window.state == GuiState.RUNNING)

    assert window.close() is True
    _wait_until(qt_app, lambda: not window.is_running)
    assert window.last_session_summary["clean_shutdown"] is True  # type: ignore[index]


def test_existing_synthetic_source_reaches_all_named_scenes() -> None:
    source = SyntheticFrameSource(
        REPO_ROOT / "test_data/m3/synthetic",
        VISION_CONFIG,
        target_fps=0,
        frames_per_scene=1,
        loop=False,
    )
    source.open()
    scenes = []
    while source.read() is not None:
        scenes.append(source.current_scene)
    source.close()

    assert source.metadata()["sequence"] == [
        "blank",
        "normal",
        "normal_hold",
        "bright",
        "dark",
        "occlusion",
        "touching",
        "blank",
    ]
    assert len(scenes) == 8
