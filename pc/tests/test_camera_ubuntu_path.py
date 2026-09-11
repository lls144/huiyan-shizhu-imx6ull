"""Configuration-only coverage for the explicit Linux camera-node path."""

from __future__ import annotations

from pathlib import Path
import unittest

from pc.camera.config import load_camera_config


class UbuntuCameraPathConfigTests(unittest.TestCase):
    def test_acepro2_config_uses_explicit_v4l2_node_and_requested_mode(self) -> None:
        config = load_camera_config(Path("pc/config/camera_ubuntu_acepro2.json"))

        self.assertEqual(config.device_path, "/dev/video2")
        self.assertEqual(config.backend, "V4L2")
        self.assertEqual(config.fourcc, "MJPG")
        self.assertEqual((config.requested_width, config.requested_height, config.requested_fps), (1920, 1080, 30.0))


if __name__ == "__main__":
    unittest.main()
