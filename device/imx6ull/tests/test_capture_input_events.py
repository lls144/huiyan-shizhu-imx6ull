"""Tests for name-based Linux input device discovery."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from device.imx6ull.scripts.capture_input_events import find_event_device


class CaptureInputEventsTests(unittest.TestCase):
    def test_finds_device_by_name_without_assuming_event_number(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sys_input = Path(directory)
            for event, name in (("event9", "other-device"), ("event4", "huiyan-keys")):
                name_path = sys_input / event / "device" / "name"
                name_path.parent.mkdir(parents=True)
                name_path.write_text(name, encoding="utf-8")
            self.assertEqual(find_event_device("huiyan-keys", sys_input), Path("/dev/input/event4"))

    def test_fails_for_missing_or_ambiguous_device_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sys_input = Path(directory)
            with self.assertRaisesRegex(RuntimeError, "not found"):
                find_event_device("huiyan-keys", sys_input)
            for event in ("event1", "event7"):
                name_path = sys_input / event / "device" / "name"
                name_path.parent.mkdir(parents=True)
                name_path.write_text("huiyan-keys", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "ambiguous"):
                find_event_device("huiyan-keys", sys_input)
