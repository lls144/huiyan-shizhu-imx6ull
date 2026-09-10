"""M9-A configuration and input-backend tests; no GPIO device is touched."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from device.imx6ull.config import ControllerConfig, load_controller_config
from device.imx6ull.controller_main import build_runtime
from device.imx6ull.core.key_input import GpioKeyInput, KeyInputStatus, KeyboardKeyInput, LinuxInputKeyInput


CONFIG_PATH = Path(__file__).parents[1] / "config" / "controller.json"


class DeploymentPreparationTests(unittest.TestCase):
    def test_committed_config_has_verified_linux_input_mapping(self) -> None:
        config = load_controller_config(CONFIG_PATH)
        self.assertEqual(config.tcp_port, 9000)
        self.assertEqual(config.fifo_capacity, 3)
        self.assertEqual(config.heartbeat_interval, 1000)
        self.assertEqual(config.gpio.to_mapping(), {"key1": 24, "key2": 25, "key3": 26})
        self.assertEqual(config.linux_input.device_name, "huiyan-keys")
        self.assertEqual(config.linux_input.to_mapping(), {148: "KEY1", 149: "KEY2", 202: "KEY3"})

    def test_invalid_config_is_rejected(self) -> None:
        payload = {
            "tcp_port": 9000,
            "fifo_capacity": 3,
            "heartbeat_interval": 1000,
            "gpio": {"key1": -1, "key2": None, "key3": None},
            "linux_input": {},
        }
        with self.assertRaisesRegex(ValueError, "gpio.key1"):
            ControllerConfig.from_dict(payload)

    def test_gpio_input_reports_not_configured_without_hardware_access(self) -> None:
        gpio = GpioKeyInput({"key1": None, "key2": None, "key3": None})
        result = gpio.poll()
        self.assertFalse(gpio.configured)
        self.assertEqual(result.status, KeyInputStatus.NOT_CONFIGURED)
        self.assertIsNone(result.key)

    def test_runtime_selects_requested_backend_from_config(self) -> None:
        config = load_controller_config(CONFIG_PATH)
        desktop = build_runtime(config, "desktop", host="127.0.0.1")
        imx6ull = build_runtime(config, "imx6ull", host="127.0.0.1")
        self.assertIsInstance(desktop.key_input, KeyboardKeyInput)
        self.assertIsInstance(imx6ull.key_input, LinuxInputKeyInput)
        self.assertEqual(desktop.server.port, config.tcp_port)
        self.assertEqual(imx6ull.key_input.poll().status, KeyInputStatus.UNAVAILABLE)

    def test_load_config_from_json_file(self) -> None:
        payload = {
            "tcp_port": 9100,
            "fifo_capacity": 4,
            "heartbeat_interval": 250,
            "gpio": {"key1": None, "key2": None, "key3": None},
            "linux_input": {"device_name": None},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "controller.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            config = load_controller_config(path)
        self.assertEqual((config.tcp_port, config.fifo_capacity, config.heartbeat_interval), (9100, 4, 250))
