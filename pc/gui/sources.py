"""Synthetic and camera frame sources sharing one minimal lifecycle contract."""

from __future__ import annotations

from dataclasses import asdict
import logging
from pathlib import Path
from typing import Any, Protocol

import cv2
import numpy as np

from pc.vision.config import VisionConfig
from pc.vision.live import LiveCamera, _camera_actual_properties, open_live_camera
from pc.vision.preprocess import Image
from pc.vision.roi import (
    CalibrationResult,
    NormalizedRoi,
    RoiMode,
    calibrate_roi,
    fixed_roi,
    load_runtime_calibration,
    save_runtime_calibration,
    select_manual_roi,
)

from .runtime import LOGGER_NAME


class FrameSource(Protocol):
    source_type: str
    target_fps: float
    roi: NormalizedRoi
    roi_mode: str
    roi_source: str
    failed_reads: int

    def open(self) -> None: ...

    def read(self) -> Image | None: ...

    def close(self) -> None: ...

    def metadata(self) -> dict[str, Any]: ...


class SyntheticFrameSource:
    """Loop existing M3 fixtures as a deterministic video-like source."""

    source_type = "synthetic"

    def __init__(
        self,
        dataset_root: Path,
        vision_config: VisionConfig,
        target_fps: float = 20.0,
        frames_per_scene: int = 20,
        loop: bool = True,
    ) -> None:
        if target_fps < 0:
            raise ValueError("synthetic target_fps must be non-negative")
        if frames_per_scene <= 0:
            raise ValueError("frames_per_scene must be positive")
        self.dataset_root = dataset_root
        self.target_fps = target_fps
        self.frames_per_scene = frames_per_scene
        self.loop = loop
        self.roi = fixed_roi(vision_config)
        self.roi_mode = "fixed_normalized"
        self.roi_source = "configured"
        self.failed_reads = 0
        self._frames: list[Image] = []
        self._scene_names: list[str] = []
        self._index = 0
        self._opened = False

    def open(self) -> None:
        names = [
            "multi_normal.png",
            "multi_normal.png",
            "multi_bright.png",
            "multi_dark.png",
            "multi_occlusion.png",
            "multi_touching.png",
        ]
        loaded: list[Image] = []
        for name in names:
            image = cv2.imread(str(self.dataset_root / name), cv2.IMREAD_COLOR)
            if image is None:
                raise RuntimeError(f"failed to read synthetic GUI source: {self.dataset_root / name}")
            loaded.append(image)
        blank = np.full_like(loaded[0], 245)
        self._frames = [blank, *loaded, blank]
        self._scene_names = ["blank", "normal", "normal_hold", "bright", "dark", "occlusion", "touching", "blank"]
        self._index = 0
        self._opened = True

    @property
    def current_scene(self) -> str:
        if not self._scene_names:
            return "not_open"
        scene_index = min(self._index // self.frames_per_scene, len(self._scene_names) - 1)
        return self._scene_names[scene_index]

    def read(self) -> Image | None:
        if not self._opened:
            raise RuntimeError("synthetic source is not open")
        total = len(self._frames) * self.frames_per_scene
        if self._index >= total:
            if not self.loop:
                return None
            self._index = 0
        scene_index = self._index // self.frames_per_scene
        frame = self._frames[scene_index]
        self._index += 1
        return frame

    def close(self) -> None:
        self._opened = False

    def metadata(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "dataset_root": str(self.dataset_root),
            "target_fps": self.target_fps,
            "frames_per_scene": self.frames_per_scene,
            "loop": self.loop,
            "sequence": list(self._scene_names),
        }


class CameraFrameSource:
    """Thin adapter around the existing M1 camera and M2 startup ROI APIs."""

    source_type = "camera"
    target_fps = 0.0

    def __init__(
        self,
        camera_config_path: Path,
        vision_config: VisionConfig,
        roi_mode: RoiMode,
        calibration_path: Path,
        reuse_calibration: bool = False,
    ) -> None:
        self.camera_config_path = camera_config_path
        self.vision_config = vision_config
        self.requested_roi_mode = roi_mode
        self.calibration_path = calibration_path
        self.reuse_calibration = reuse_calibration
        self.roi = fixed_roi(vision_config)
        self.roi_mode = "fixed_normalized"
        self.roi_source = "not_calibrated"
        self.failed_reads = 0
        self.live_camera: LiveCamera | None = None
        self.calibration: CalibrationResult | None = None
        self._first_frame: Image | None = None
        self._consecutive_failures = 0

    def open(self) -> None:
        logger = logging.getLogger(LOGGER_NAME)
        logger.info("camera opening config=%s", self.camera_config_path)
        try:
            self._open()
            logger.info("camera open success device=%s", self.live_camera.device.name)
        except Exception:
            logger.exception("camera open failed")
            raise

    def _open(self) -> None:
        self.live_camera = open_live_camera(self.camera_config_path)
        first_frame: Image | None = None
        for _ in range(self.live_camera.config.warmup_frames + 1):
            success, candidate = self.live_camera.capture.read()
            if success:
                first_frame = candidate
        if first_frame is None:
            self.close()
            raise RuntimeError("camera opened but no frame was received during warmup")
        if self.reuse_calibration and self.calibration_path.exists():
            calibration = load_runtime_calibration(self.calibration_path, first_frame.shape)
        else:
            calibration = calibrate_roi(
                first_frame,
                self.vision_config,
                self.requested_roi_mode,
                lambda image: select_manual_roi(image, self.vision_config),
                print,
            )
        save_runtime_calibration(calibration, first_frame.shape, self.calibration_path)
        self.calibration = calibration
        self.roi = calibration.roi
        self.roi_mode = calibration.selected_mode
        self.roi_source = calibration.source
        self._first_frame = first_frame

    def read(self) -> Image | None:
        if self.live_camera is None:
            raise RuntimeError("camera source is not open")
        if self._first_frame is not None:
            frame = self._first_frame
            self._first_frame = None
            return frame
        while True:
            success, frame = self.live_camera.capture.read()
            if success:
                self._consecutive_failures = 0
                return frame
            self.failed_reads += 1
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.vision_config.live_max_consecutive_read_failures:
                raise RuntimeError(
                    f"camera read failed {self._consecutive_failures} consecutive times"
                )

    def close(self) -> None:
        if self.live_camera is not None:
            self.live_camera.capture.release()
        self.live_camera = None
        self._first_frame = None

    def metadata(self) -> dict[str, Any]:
        if self.live_camera is None:
            return {"source_type": self.source_type, "camera_config_path": str(self.camera_config_path)}
        return {
            "source_type": self.source_type,
            "camera_config_path": str(self.camera_config_path),
            "device": asdict(self.live_camera.device),
            "camera_config": asdict(self.live_camera.config),
            "actual_properties": _camera_actual_properties(self.live_camera.capture),
            "calibration": self.calibration.to_dict() if self.calibration is not None else None,
        }
