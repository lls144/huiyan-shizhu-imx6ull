"""OpenCV live preview that reuses M1 camera ownership and the M2 core pipeline."""

from __future__ import annotations

import json
import subprocess
import time
from collections import Counter, deque
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2

from pc.camera.capture import open_configured_camera
from pc.camera.config import CameraConfig, load_camera_config
from pc.camera.devices import CameraDevice, enumerate_camera_devices, select_camera_device

from .config import VisionConfig
from .pipeline import ImageAnalysis, analyze_image, annotated_image
from .preprocess import Image
from .reporting import write_image
from .roi import (
    CalibrationResult,
    NormalizedRoi,
    RoiMode,
    calibrate_roi,
    load_runtime_calibration,
    save_runtime_calibration,
    select_manual_roi,
)


@dataclass
class LiveCamera:
    """M1-owned capture plus the resolved device and configuration."""

    capture: cv2.VideoCapture
    device: CameraDevice
    config: CameraConfig


class StableLabelFilter:
    """Display-only majority vote; raw per-frame results remain unchanged."""

    def __init__(self, window_size: int, minimum_votes: int) -> None:
        if window_size <= 0 or not 0 < minimum_votes <= window_size:
            raise ValueError("invalid label stability settings")
        self._labels: deque[str] = deque(maxlen=window_size)
        self._minimum_votes = minimum_votes
        self.stable_label = "no_object"

    def update(self, raw_label: str) -> str:
        self._labels.append(raw_label)
        counts = Counter(self._labels)
        latest_index = {label: index for index, label in enumerate(self._labels)}
        candidate = max(counts, key=lambda label: (counts[label], latest_index[label]))
        if counts[candidate] >= self._minimum_votes:
            self.stable_label = candidate
        return self.stable_label

    def reset(self) -> None:
        self._labels.clear()
        self.stable_label = "no_object"


class FpsMeter:
    def __init__(self, window_size: int) -> None:
        if window_size <= 1:
            raise ValueError("FPS window must be greater than one")
        self._timestamps: deque[float] = deque(maxlen=window_size)

    def update(self, timestamp: float | None = None) -> float:
        self._timestamps.append(timestamp if timestamp is not None else time.perf_counter())
        if len(self._timestamps) < 2:
            return 0.0
        duration = self._timestamps[-1] - self._timestamps[0]
        return (len(self._timestamps) - 1) / duration if duration > 0 else 0.0


def open_live_camera(camera_config_path: Path) -> LiveCamera:
    """Resolve and open a camera strictly through the existing M1 functions.

    A configured ``device_path`` is an intentional platform-specific override
    (for example Linux ``/dev/video2``).  It avoids ambiguous index selection;
    name/index enumeration remains the unchanged default for existing configs.
    """

    camera_config = load_camera_config(camera_config_path)
    if camera_config.device_path is not None:
        from pc.camera.devices import resolve_backend

        backend_name = camera_config.backend.strip().upper()
        device = CameraDevice(
            index=camera_config.device_path,
            name=camera_config.device_name or camera_config.device_path,
            path=camera_config.device_path,
            vid=None,
            pid=None,
            backend_name=backend_name,
            backend_id=resolve_backend(backend_name),
        )
    else:
        devices = enumerate_camera_devices(camera_config.backend)
        device = select_camera_device(devices, camera_config.device_name, camera_config.fallback_index)
    capture = open_configured_camera(device, camera_config)
    return LiveCamera(capture, device, camera_config)


def process_live_frame(frame: Image, config: VisionConfig, roi: NormalizedRoi) -> ImageAnalysis:
    """Use the exact offline core with only a runtime ROI override."""

    return analyze_image(frame, config, roi)


def contour_center(analysis: ImageAnalysis) -> tuple[int, int] | None:
    selected = analysis.selected_candidate
    if selected is None:
        return None
    moments = cv2.moments(selected.contour)
    if moments["m00"] == 0:
        return None
    left, top, _, _ = analysis.preprocessing.roi_bounds
    x = round(moments["m10"] / moments["m00"]) + left
    y = round(moments["m01"] / moments["m00"]) + top
    return x, y


def render_live_overlay(
    frame: Image,
    analysis: ImageAnalysis,
    stable_label: str,
    fps: float,
    calibration: CalibrationResult,
) -> Image:
    """Draw a compact live overlay with raw and stabilized states."""

    output = annotated_image(frame, analysis, draw_summary=False)
    selected = analysis.selected_candidate
    center = contour_center(analysis)
    if selected is not None:
        roi_left, roi_top, _, _ = analysis.preprocessing.roi_bounds
        x, y, width, height = selected.features.bounding_box
        cv2.rectangle(
            output,
            (x + roi_left, y + roi_top),
            (x + roi_left + width - 1, y + roi_top + height - 1),
            (0, 200, 255),
            2,
        )
    if center is not None:
        cv2.drawMarker(output, center, (255, 255, 0), cv2.MARKER_CROSS, 22, 2)
    vertices = selected.features.vertices if selected else 0
    circularity = selected.features.circularity if selected else 0.0
    area_ratio = selected.features.area_ratio if selected else 0.0
    lines = [
        f"raw={analysis.label}  stable={stable_label}  confidence={analysis.confidence:.3f}",
        f"vertices={vertices}  area_ratio={area_ratio:.3f}  circularity={circularity:.3f}",
        f"FPS={fps:.1f}  ROI={calibration.selected_mode}/{calibration.source}",
        "keys: R recalibrate | S save evidence | Q/ESC quit",
    ]
    for index, text in enumerate(lines):
        y = 32 + index * 30
        cv2.putText(output, text, (18, y), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (0, 0, 0), 4)
        cv2.putText(output, text, (18, y), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2)
    return output


def _git_state() -> dict[str, object]:
    repo_root = Path(__file__).resolve().parents[2]
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        return {"commit": commit, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError) as error:
        return {"commit": None, "dirty": None, "error": f"{type(error).__name__}: {error}"}


def _timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def _filename_timestamp() -> str:
    return datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")


def _camera_actual_properties(capture: cv2.VideoCapture) -> dict[str, object]:
    try:
        backend = capture.getBackendName()
    except cv2.error:
        backend = None
    return {
        "width": capture.get(cv2.CAP_PROP_FRAME_WIDTH),
        "height": capture.get(cv2.CAP_PROP_FRAME_HEIGHT),
        "reported_fps": capture.get(cv2.CAP_PROP_FPS),
        "backend": backend,
    }


def _selected_measurements(analysis: ImageAnalysis) -> dict[str, object]:
    selected = analysis.selected_candidate
    if selected is None:
        return {
            "vertices": None,
            "contour_area": None,
            "area_ratio": None,
            "solidity": None,
            "circularity": None,
            "center": None,
        }
    return {
        "vertices": selected.features.vertices,
        "contour_area": selected.features.area,
        "area_ratio": selected.features.area_ratio,
        "solidity": selected.features.solidity,
        "circularity": selected.features.circularity,
        "center": list(contour_center(analysis)) if contour_center(analysis) is not None else None,
    }


def save_live_evidence(
    frame: Image,
    analysis: ImageAnalysis,
    annotated: Image,
    stable_label: str,
    fps: float,
    calibration: CalibrationResult,
    camera: LiveCamera,
    vision_config: VisionConfig,
    evidence_root: Path,
) -> Path:
    """Save the six requested artifacts for one user-triggered frame."""

    evidence_dir = evidence_root / _filename_timestamp()
    write_image(evidence_dir / "frame.jpg", frame)
    write_image(evidence_dir / "roi.jpg", analysis.preprocessing.roi)
    write_image(evidence_dir / "binary.png", analysis.preprocessing.binary)
    write_image(evidence_dir / "canny.png", analysis.preprocessing.canny)
    write_image(evidence_dir / "annotated.jpg", annotated)
    height, width = frame.shape[:2]
    payload = {
        "schema_version": 1,
        "timestamp": _timestamp(),
        "git": _git_state(),
        "camera_device": asdict(camera.device),
        "camera_config": asdict(camera.config),
        "camera_actual_properties": _camera_actual_properties(camera.capture),
        "frame_resolution": {"width": width, "height": height},
        "roi_mode": calibration.selected_mode,
        "roi_source": calibration.source,
        "normalized_roi": calibration.roi.to_dict(),
        "pixel_roi": list(analysis.preprocessing.roi_bounds),
        "predicted_class": analysis.label,
        "stable_display_class": stable_label,
        "confidence": analysis.confidence,
        "passed_contour_filter": analysis.selected_candidate is not None,
        "display_fps": fps,
        **_selected_measurements(analysis),
        "otsu_threshold": analysis.preprocessing.otsu_threshold,
        "vision_config_snapshot": asdict(vision_config),
        "artifacts": {
            "frame": "frame.jpg",
            "roi": "roi.jpg",
            "binary": "binary.png",
            "canny": "canny.png",
            "annotated": "annotated.jpg",
        },
    }
    json_path = evidence_dir / "evidence.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return json_path


def _write_session_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_live_session(
    camera_config_path: Path,
    vision_config: VisionConfig,
    requested_roi_mode: RoiMode,
    calibration_path: Path,
    evidence_root: Path,
    reuse_calibration: bool = False,
) -> int:
    """Run one real preview session; ROI changes only at startup or on R."""

    camera = open_live_camera(camera_config_path)
    capture = camera.capture
    session_started = time.perf_counter()
    session_path = evidence_root / f"session-{_filename_timestamp()}.json"
    frames_processed = 0
    failed_reads = 0
    consecutive_failures = 0
    evidence_saved = 0
    processing_started: float | None = None
    completed_normally = False
    session_error: str | None = None
    calibration_history: list[dict[str, object]] = []
    session_report: dict[str, Any] = {
        "schema_version": 1,
        "status": "starting",
        "started_at": _timestamp(),
        "git": _git_state(),
        "camera_device": asdict(camera.device),
        "camera_config": asdict(camera.config),
        "camera_actual_properties": _camera_actual_properties(capture),
        "requested_roi_mode": requested_roi_mode,
        "calibration_file": str(calibration_path),
        "calibration_history": calibration_history,
    }
    _write_session_report(session_path, session_report)

    try:
        first_frame: Image | None = None
        for _ in range(camera.config.warmup_frames + 1):
            success, candidate = capture.read()
            if success:
                first_frame = candidate
        if first_frame is None:
            raise RuntimeError("camera opened but no frame was received during warmup")

        if reuse_calibration and calibration_path.exists():
            calibration = load_runtime_calibration(calibration_path, first_frame.shape)
            print(f"restored runtime ROI from {calibration_path}: {calibration.roi.to_dict()}")
        else:
            if reuse_calibration:
                print(f"requested saved ROI does not exist: {calibration_path}; starting calibration")
            calibration = calibrate_roi(
                first_frame,
                vision_config,
                requested_roi_mode,
                lambda image: select_manual_roi(image, vision_config),
                print,
            )
        save_runtime_calibration(calibration, first_frame.shape, calibration_path)
        calibration_history.append({"timestamp": _timestamp(), **calibration.to_dict()})
        session_report["status"] = "running"
        session_report["runtime_roi"] = calibration.to_dict()
        _write_session_report(session_path, session_report)

        stabilizer = StableLabelFilter(
            vision_config.stability_window_size,
            vision_config.stability_min_votes,
        )
        fps_meter = FpsMeter(vision_config.fps_smoothing_window)
        frame = first_frame
        window_name = "Huiyan Shizhu M2 Live"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(
            window_name,
            vision_config.live_preview_width,
            vision_config.live_preview_height,
        )
        processing_started = time.perf_counter()
        while True:
            analysis = process_live_frame(frame, vision_config, calibration.roi)
            stable_label = stabilizer.update(analysis.label)
            fps = fps_meter.update()
            annotated = render_live_overlay(frame, analysis, stable_label, fps, calibration)
            cv2.imshow(window_name, annotated)
            frames_processed += 1
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q"), 27):
                break
            if key in (ord("r"), ord("R")):
                print("ROI recalibration requested; classification is paused until calibration completes")
                calibration = calibrate_roi(
                    frame,
                    vision_config,
                    requested_roi_mode,
                    lambda image: select_manual_roi(image, vision_config),
                    print,
                )
                save_runtime_calibration(calibration, frame.shape, calibration_path)
                calibration_history.append({"timestamp": _timestamp(), **calibration.to_dict()})
                session_report["runtime_roi"] = calibration.to_dict()
                stabilizer.reset()
                _write_session_report(session_path, session_report)
            elif key in (ord("s"), ord("S")):
                evidence_path = save_live_evidence(
                    frame,
                    analysis,
                    annotated,
                    stable_label,
                    fps,
                    calibration,
                    camera,
                    vision_config,
                    evidence_root,
                )
                evidence_saved += 1
                print(f"saved live evidence: {evidence_path}")

            success, next_frame = capture.read()
            if success:
                frame = next_frame
                consecutive_failures = 0
            else:
                failed_reads += 1
                consecutive_failures += 1
                if consecutive_failures >= vision_config.live_max_consecutive_read_failures:
                    raise RuntimeError(
                        f"camera read failed {consecutive_failures} consecutive times"
                    )

        completed_normally = True
        return 0
    except Exception as error:
        session_error = f"{type(error).__name__}: {error}"
        raise
    finally:
        elapsed = time.perf_counter() - session_started
        processing_elapsed = (
            time.perf_counter() - processing_started if processing_started is not None else 0.0
        )
        capture.release()
        cv2.destroyAllWindows()
        session_report.update(
            {
                "status": "completed" if completed_normally else "failed",
                "finished_at": _timestamp(),
                "duration_seconds": round(elapsed, 6),
                "active_processing_seconds": round(processing_elapsed, 6),
                "frames_processed": frames_processed,
                "failed_reads": failed_reads,
                "measured_processing_fps": (
                    round(frames_processed / processing_elapsed, 6) if processing_elapsed else 0.0
                ),
                "evidence_frames_saved": evidence_saved,
                "error": session_error,
            }
        )
        _write_session_report(session_path, session_report)
