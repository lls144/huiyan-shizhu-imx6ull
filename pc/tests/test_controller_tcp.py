"""M7 localhost TCP integration tests; no hardware controller is required."""

from __future__ import annotations

import json
import socket
import time
import unittest

from device.imx6ull.network.tcp_server import DesktopControllerServer
from pc.communication.controller_client import ControllerClient


class ControllerTcpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = DesktopControllerServer(port=0)
        self.server.start()

    def tearDown(self) -> None:
        self.server.close()

    def _raw_exchange(self, payload: bytes) -> dict[str, object]:
        _, port = self.server.address
        with socket.create_connection(("127.0.0.1", port), timeout=1.0) as peer:
            peer.settimeout(1.0)
            peer.sendall(payload)
            received = bytearray()
            while b"\n" not in received:
                received.extend(peer.recv(4096))
        return json.loads(received.partition(b"\n")[0].decode("utf-8"))


    def _client(self) -> ControllerClient:
        _, port = self.server.address
        client = ControllerClient(port=port, ack_timeout=0.1, reconnect_delay=0.02, max_retries=3)
        client.start()
        self.assertTrue(client.wait_connected())
        return client


    def test_enqueue_success_and_heartbeat(self) -> None:
        client = self._client()
        try:
            accepted = client.send_enqueue(1, "circle", source_event_id=7, source_object_id=3).result(1.0)
            self.assertEqual(accepted["type"], "ack")
            self.assertEqual(accepted["status"], "accepted")
            self.assertEqual(accepted["command_id"], 1)
            self.assertEqual(client.send_heartbeat().result(1.0)["status"], "alive")
        finally:
            client.close()


    def test_malformed_json_returns_error(self) -> None:
        response = self._raw_exchange(b'{"version":1,"type":"enqueue"\n')
        self.assertEqual(response["type"], "error")
        self.assertEqual(response["code"], "MALFORMED_JSON")


    def test_unknown_type_returns_error(self) -> None:
        response = self._raw_exchange(b'{"version":1,"type":"turn_on_gpio","request_id":"unknown-1"}\n')
        self.assertEqual(response["type"], "error")
        self.assertEqual(response["code"], "UNKNOWN_TYPE")
        self.assertEqual(response["request_id"], "unknown-1")


    def test_invalid_shape_returns_error(self) -> None:
        response = self._raw_exchange(b'{"version":1,"type":"enqueue","request_id":"shape-1","command_id":1,"shape":"hexagon"}\n')
        self.assertEqual(response["type"], "error")
        self.assertEqual(response["code"], "INVALID_SHAPE")


    def test_duplicate_command_id_returns_duplicate_ack(self) -> None:
        client = self._client()
        try:
            self.assertEqual(client.send_enqueue(9, "triangle").result(1.0)["status"], "accepted")
            self.assertEqual(client.send_enqueue(9, "triangle").result(1.0)["status"], "duplicate")
        finally:
            client.close()


    def test_disconnect_reconnect_retries_pending_enqueue(self) -> None:
        client = self._client()
        try:
            self.assertEqual(client.send_enqueue(1, "rectangle").result(1.0)["status"], "accepted")
            self.server.disconnect_clients()
            deadline = time.monotonic() + 1.0
            while client.wait_connected(0.01) and time.monotonic() < deadline:
                time.sleep(0.01)
            response = client.send_enqueue(2, "circle").result(1.5)
            self.assertEqual(response["status"], "accepted")
            self.assertTrue(client.wait_connected(1.0))
        finally:
            client.close()
