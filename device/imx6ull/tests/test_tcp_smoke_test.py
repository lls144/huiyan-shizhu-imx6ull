"""Run the dependency-free smoke vector against a real TCP listener object."""

from __future__ import annotations

import unittest

from device.imx6ull.network.tcp_server import DesktopControllerServer
from device.imx6ull.scripts.tcp_smoke_test import run_smoke


class TcpSmokeTestTests(unittest.TestCase):
    def test_full_smoke_vector(self) -> None:
        server = DesktopControllerServer(host="127.0.0.1", port=0)
        server.start()
        try:
            host, port = server.address
            results = run_smoke(host, port)
        finally:
            server.close()
        self.assertEqual([label for label, _ in results], [
            "heartbeat",
            "pipeline_state",
            "enqueue triangle",
            "enqueue circle",
            "enqueue rectangle",
            "FIFO full",
            "duplicate command_id",
            "reset",
            "FIFO order via key_event protocol",
            "reconnect",
        ])
