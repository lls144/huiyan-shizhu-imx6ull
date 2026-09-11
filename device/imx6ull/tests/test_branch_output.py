"""M9 output abstraction tests; all LED paths are temporary local files."""

from __future__ import annotations

import grp
import os
import socket
import threading
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List

from device.imx6ull.core.controller import ControllerCore
from device.imx6ull.core.models import BranchOutputEvent, Key, OutputEvent, OutputOffEvent
from device.imx6ull.output.branch_output import BranchOutputDispatcher, IBranchOutputBackend, UnixSocketBranchOutputBackend
from device.imx6ull.output.led_helper import LED_NAMES, LedClassWriter, LedHelper, LedHelperConfig
from device.imx6ull.output.protocol import OutputProtocolError, decode_output_event, encode_output_event


class _RecordingBackend(IBranchOutputBackend):
    def __init__(self) -> None:
        self.events = []  # type: List[OutputEvent]
        self.called = threading.Event()

    def send(self, event: OutputEvent) -> None:
        self.events.append(event)
        self.called.set()


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class BranchOutputEventTests(unittest.TestCase):
    def test_completed_sorts_emit_the_expected_branch_events(self) -> None:
        for shape, keys, branch in (
            ("triangle", (Key.KEY1,), "Branch1"),
            ("circle", (Key.KEY1, Key.KEY2), "Branch2"),
            ("rectangle", (Key.KEY1, Key.KEY2, Key.KEY3), "Branch3"),
        ):
            with self.subTest(shape=shape):
                core = ControllerCore()
                core.enqueue(1, shape)
                for key in keys:
                    core.handle_key(key)
                self.assertEqual(core.drain_output_events(), (BranchOutputEvent(branch),))

    def test_reset_emits_immediate_off(self) -> None:
        core = ControllerCore()
        core.enqueue(1, "triangle")
        core.handle_key(Key.KEY1)
        core.drain_output_events()
        core.reset()
        self.assertEqual(core.drain_output_events(), (OutputOffEvent(),))

    def test_enqueue_station_move_and_wrong_station_emit_nothing(self) -> None:
        core = ControllerCore()
        self.assertEqual(core.enqueue(1, "circle").status, "accepted")
        self.assertEqual(core.drain_output_events(), ())
        self.assertEqual(core.handle_key(Key.KEY2).status, "wrong_station")
        self.assertEqual(core.drain_output_events(), ())
        self.assertEqual(core.handle_key(Key.KEY1).status, "moved")
        self.assertEqual(core.drain_output_events(), ())

    def test_dispatcher_delivers_branch_to_backend_off_main_path(self) -> None:
        backend = _RecordingBackend()
        dispatcher = BranchOutputDispatcher(backend)
        try:
            dispatcher.submit(BranchOutputEvent("Branch1"))
            self.assertTrue(backend.called.wait(1.0))
            self.assertEqual(backend.events, [BranchOutputEvent("Branch1")])
            self.assertIsNone(dispatcher.last_error)
        finally:
            dispatcher.close()

    def test_protocol_round_trip_and_helper_rejects_capability_expansion(self) -> None:
        for event in (BranchOutputEvent("Branch1"), BranchOutputEvent("Branch2"), BranchOutputEvent("Branch3"), OutputOffEvent()):
            with self.subTest(event=event):
                self.assertEqual(decode_output_event(encode_output_event(event)), event)
        invalid_messages = (
            b'{"branch":"Branch1","type":"branch","version":1,"brightness":255}\n',
            b'{"branch":"Branch4","type":"branch","version":1}\n',
            b'{"type":"off","version":true}\n',
            b'{"type":"gpio","version":1}\n',
        )
        for message in invalid_messages:
            with self.subTest(message=message):
                with self.assertRaises(OutputProtocolError):
                    decode_output_event(message)


class LedHelperTests(unittest.TestCase):
    def _make_writer(self, directory: Path) -> LedClassWriter:
        for name in LED_NAMES:
            brightness = directory / name / "brightness"
            brightness.parent.mkdir(parents=True)
            brightness.write_text("0", encoding="ascii")
        return LedClassWriter(directory)

    @staticmethod
    def _brightness(directory: Path) -> Dict[str, str]:
        return {name: (directory / name / "brightness").read_text(encoding="ascii") for name in LED_NAMES}

    def test_branch_modes_and_new_branch_replaces_output_timer(self) -> None:
        clock = _Clock()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            helper = LedHelper(self._make_writer(root), duration_ms=1000, clock=clock)
            helper.handle_event(BranchOutputEvent("Branch1"))
            self.assertEqual(self._brightness(root), {"red": "255", "green": "0", "blue": "0"})
            clock.advance(0.8)
            self.assertFalse(helper.tick())
            helper.handle_event(BranchOutputEvent("Branch2"))
            self.assertEqual(self._brightness(root), {"red": "255", "green": "255", "blue": "0"})
            clock.advance(0.8)
            self.assertFalse(helper.tick())
            self.assertEqual(self._brightness(root), {"red": "255", "green": "255", "blue": "0"})
            clock.advance(0.2)
            self.assertTrue(helper.tick())
            self.assertEqual(self._brightness(root), {"red": "0", "green": "0", "blue": "0"})

    def test_socket_client_delivers_branch_and_invalid_command_has_no_effect(self) -> None:
        group = grp.getgrgid(os.getgid()).gr_name
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            socket_path = root / "run" / "helper.sock"
            helper = LedHelper(self._make_writer(root / "leds"), duration_ms=1000)
            helper.start_socket(LedHelperConfig(socket_path, 0o600, group, 1000))
            try:
                worker = threading.Thread(target=helper.serve_once, kwargs={"timeout": 1.0})
                worker.start()
                UnixSocketBranchOutputBackend(str(socket_path)).send(BranchOutputEvent("Branch3"))
                worker.join(1.0)
                self.assertFalse(worker.is_alive())
                self.assertEqual(helper.last_event, BranchOutputEvent("Branch3"))
                self.assertEqual(self._brightness(root / "leds"), {"red": "255", "green": "255", "blue": "255"})

                worker = threading.Thread(target=helper.serve_once, kwargs={"timeout": 1.0})
                worker.start()
                client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                try:
                    client.connect(str(socket_path))
                    client.sendall(b'{"type":"gpio","version":1}\n')
                finally:
                    client.close()
                worker.join(1.0)
                self.assertFalse(worker.is_alive())
                self.assertEqual(helper.last_event, BranchOutputEvent("Branch3"))
                self.assertEqual(self._brightness(root / "leds"), {"red": "255", "green": "255", "blue": "255"})
            finally:
                helper.close()

    def test_off_clears_active_output_without_waiting_for_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            helper = LedHelper(self._make_writer(root), duration_ms=1000)
            helper.handle_event(BranchOutputEvent("Branch3"))
            helper.handle_event(OutputOffEvent())
            self.assertEqual(self._brightness(root), {"red": "0", "green": "0", "blue": "0"})
