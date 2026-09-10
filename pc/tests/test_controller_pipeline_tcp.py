"""M8 TCP adapter test: server delegates key events to the controller core."""

from __future__ import annotations

import unittest

from device.imx6ull.network.tcp_server import DesktopControllerServer
from pc.communication.controller_client import ControllerClient, ControllerClientError


class ControllerPipelineTcpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = DesktopControllerServer(port=0)
        self.server.start()
        _, port = self.server.address
        self.client = ControllerClient(port=port, ack_timeout=0.1, reconnect_delay=0.02)
        self.client.start()
        self.assertTrue(self.client.wait_connected())

    def tearDown(self) -> None:
        self.client.close()
        self.server.close()

    def test_circle_moves_then_sorts_over_tcp(self) -> None:
        accepted = self.client.send_enqueue(12, "circle").result(1.0)
        self.assertEqual(accepted["status"], "accepted")
        self.assertEqual(accepted["pipeline_state"]["station"], "Station1")
        moved = self.client.send_key_event("KEY1").result(1.0)
        self.assertEqual(moved["type"], "pipeline_state")
        self.assertEqual(moved["state"], "Station2")
        sorted_result = self.client.send_key_event("KEY2").result(1.0)
        self.assertEqual(sorted_result["type"], "sorted")
        self.assertEqual(sorted_result["branch"], "Branch2")
        self.assertEqual(sorted_result["command"]["command_id"], 12)
        self.assertTrue(sorted_result["pipeline_state"]["empty"])

    def test_wrong_station_is_a_protocol_error_without_state_change(self) -> None:
        self.client.send_enqueue(13, "circle").result(1.0)
        with self.assertRaisesRegex(ControllerClientError, "WRONG_STATION"):
            self.client.send_key_event("KEY2").result(1.0)
        state = self.client.request_pipeline_state().result(1.0)
        self.assertEqual(state["state"], "Station1")
        self.assertEqual(state["pipeline_state"]["queue_length"], 1)
