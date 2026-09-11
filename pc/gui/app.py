"""Command-line launcher for the M5 PySide6 desktop application."""

from __future__ import annotations

import argparse
import os
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Sequence

from pc.communication.state_monitor import BoardStateMonitor, ConnectionStatus
from pc.communication.vision_bridge import VisionEventEnqueuer, load_controller_connection_config
from pc.communication.vision_dispatcher import VisionEventDispatcher
from pc.events.config import load_event_config
from pc.vision.config import load_vision_config
from pc.vision.pipeline import analyze_multiple_objects

from .reporting import write_csv_record, write_json_record
from .sources import CameraFrameSource, SyntheticFrameSource


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("synthetic", "camera"), default="synthetic")
    parser.add_argument("--vision-config", type=Path, default=Path("pc/config/vision.json"))
    parser.add_argument("--event-config", type=Path, default=Path("pc/config/events.json"))
    parser.add_argument(
        "--controller-config",
        type=Path,
        default=Path("pc/config/controller_windows_ethernet.json"),
        help="Windows RJ45 Controller profile used by the Board State monitor",
    )
    parser.add_argument(
        "--command-id-start",
        type=int,
        help="optional positive start ID for this Camera-to-Controller GUI session",
    )
    parser.add_argument("--camera-config", type=Path, default=Path("pc/config/camera.json"))
    parser.add_argument(
        "--roi-mode", choices=("auto", "manual", "fixed_normalized"), default="auto"
    )
    parser.add_argument(
        "--calibration-file", type=Path, default=Path("output/m5/runtime-calibration.json")
    )
    parser.add_argument("--reuse-calibration", action="store_true")
    parser.add_argument("--dataset-root", type=Path, default=Path("test_data/m3/synthetic"))
    parser.add_argument("--synthetic-fps", type=float, default=20.0)
    parser.add_argument("--frames-per-scene", type=int, default=20)
    parser.add_argument("--no-loop", action="store_true")
    parser.add_argument("--session-dir", type=Path, default=Path("output/m5/sessions"))
    parser.add_argument("--m3-evidence-dir", type=Path, default=Path("output/m3/live-evidence"))
    parser.add_argument(
        "--expected-labels",
        nargs="*",
        choices=("triangle", "rectangle", "circle"),
        default=("triangle", "rectangle", "circle"),
    )
    parser.add_argument("--no-auto-start", action="store_true")
    parser.add_argument("--offscreen", action="store_true")
    parser.add_argument("--soak-seconds", type=float, default=0.0)
    parser.add_argument("--summary-json", type=Path)
    parser.add_argument("--summary-csv", type=Path)
    parser.add_argument("--screenshot", type=Path)
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.offscreen:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from .window import MainWindow

    vision_config = load_vision_config(args.vision_config)
    event_config = load_event_config(args.event_config)
    controller_connection = load_controller_connection_config(args.controller_config)
    controller_client = controller_connection.make_client()
    board_monitor = BoardStateMonitor(
        controller_client,
        request_timeout=(
            controller_connection.connect_timeout
            + controller_connection.ack_timeout * (controller_connection.max_retries + 1)
            + controller_connection.reconnect_delay
        ),
    )
    event_dispatcher = None
    if args.source == "camera":
        command_id_start = args.command_id_start or int(time.time() * 1000)
        if command_id_start < 1:
            parser.error("--command-id-start must be positive")
        event_dispatcher = VisionEventDispatcher(
            VisionEventEnqueuer(
                controller_client,
                command_id_start,
                result_timeout=controller_connection.ack_timeout
                * (controller_connection.max_retries + 2),
            ),
            board_online=lambda: board_monitor.snapshot.connection is ConnectionStatus.ONLINE,
        )

    if args.source == "synthetic":
        source_factory = lambda: SyntheticFrameSource(
            args.dataset_root,
            vision_config,
            target_fps=args.synthetic_fps,
            frames_per_scene=args.frames_per_scene,
            loop=not args.no_loop,
        )
    else:
        source_factory = lambda: CameraFrameSource(
            args.camera_config,
            vision_config,
            args.roi_mode,
            args.calibration_file,
            args.reuse_calibration,
        )

    app = QApplication.instance() or QApplication([sys.argv[0]])
    window = MainWindow(
        source_factory=source_factory,
        source_type=args.source,
        vision_config=vision_config,
        event_config=event_config,
        session_dir=args.session_dir,
        evidence_root=args.m3_evidence_dir,
        expected_labels=args.expected_labels,
        analyzer=analyze_multiple_objects,
        board_monitor=board_monitor,
        event_dispatcher=event_dispatcher,
    )
    window.show()
    if not args.no_auto_start:
        QTimer.singleShot(0, window.start_session)

    if args.soak_seconds > 0:
        tracemalloc.start()

        def finish_soak() -> None:
            current_bytes, peak_bytes = tracemalloc.get_traced_memory()
            window.session_annotations.update(
                {
                    "requested_soak_seconds": args.soak_seconds,
                    "python_traced_current_bytes": current_bytes,
                    "python_traced_peak_bytes": peak_bytes,
                    "screenshot": str(args.screenshot) if args.screenshot else None,
                }
            )
            window.stop_session(block=True)
            if args.screenshot is not None:
                args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                if not window.grab().save(str(args.screenshot)):
                    window.session_annotations["screenshot_error"] = "QWidget.grab save failed"
            tracemalloc.stop()
            app.quit()

        QTimer.singleShot(max(1, round(args.soak_seconds * 1000)), finish_soak)

    exit_code = app.exec()
    if window.is_running:
        window.stop_session(block=True)
    record = window.last_session_summary
    if record is not None:
        if args.summary_json is not None:
            write_json_record(record, args.summary_json)
        if args.summary_csv is not None:
            write_csv_record(record, args.summary_csv)
    if record is not None and record.get("error"):
        return 1
    return exit_code


def main() -> int:
    return run()
