"""Controller TCP adapter tests for M10 without importing PySide2."""

from __future__ import annotations

import time
import unittest

from device.imx6ull.core.controller import ControllerCore
from device.imx6ull.hmi.state_client import ControllerStateClient
from device.imx6ull.network.tcp_server import DesktopControllerServer


def _wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


class ControllerStateClientTests(unittest.TestCase):
    def setUp(self):
        self.server = DesktopControllerServer("127.0.0.1", 0, core=ControllerCore())
        self.server.start()
        _, port = self.server.address
        self.client = ControllerStateClient("127.0.0.1", port, request_timeout=0.1, heartbeat_interval=0.05)

    def tearDown(self):
        self.client.close()
        self.server.close()

    def test_online_state_and_reset_use_existing_tcp_protocol(self):
        self.server.core.enqueue(11, "triangle")
        self.client.refresh()
        self.assertTrue(_wait_until(lambda: self.client.snapshot().online and self.client.snapshot().pipeline_state is not None))
        state = self.client.snapshot().pipeline_state
        self.assertEqual(state["queue"][0]["shape"], "triangle")
        self.client.request_reset()
        self.assertTrue(
            _wait_until(
                lambda: self.client.snapshot().online
                and self.client.snapshot().pipeline_state is not None
                and self.client.snapshot().pipeline_state["queue_length"] == 0
            )
        )

    def test_offline_controller_does_not_block_or_crash(self):
        self.server.close()
        self.client.refresh()
        self.assertTrue(_wait_until(lambda: not self.client.snapshot().online))
        self.assertTrue(self.client.snapshot().error)
