"""Linux input backend tests using a pipe, never an actual input device."""

from __future__ import annotations

import os
import unittest

from device.imx6ull.core.key_input import KeyInputStatus, LinuxInputKeyInput
from device.imx6ull.core.models import Key


class LinuxInputKeyInputTests(unittest.TestCase):
    def test_press_is_delivered_once_and_release_or_repeat_is_not(self) -> None:
        read_fd, write_fd = os.pipe()
        backend = LinuxInputKeyInput("huiyan-keys", {148: Key.KEY1})
        backend._descriptor = read_fd
        try:
            events = b"".join(
                backend._INPUT_EVENT.pack(0, 0, 1, 148, value) for value in (1, 2, 0)
            )
            os.write(write_fd, events)
            result = backend.poll()
            self.assertEqual((result.status, result.key), (KeyInputStatus.EVENT, Key.KEY1))
            self.assertEqual(backend.poll().status, KeyInputStatus.NO_EVENT)
        finally:
            os.close(write_fd)
            backend._close()

    def test_unconfigured_backend_does_not_touch_linux_input(self) -> None:
        backend = LinuxInputKeyInput(None, {148: Key.KEY1})
        result = backend.poll()
        self.assertEqual(result.status, KeyInputStatus.NOT_CONFIGURED)
        self.assertIsNone(result.key)
