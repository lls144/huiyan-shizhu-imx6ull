#!/usr/bin/env python3
"""Dependency-free TCP smoke test for a running Huiyan controller."""

from __future__ import print_function

import argparse
import json
import socket
import sys
from typing import Any, Dict, List, Tuple


def _request(sock, request_id, message_type, **payload):
    # type: (socket.socket, str, str, Any) -> Dict[str, Any]
    message = {"version": 1, "type": message_type, "request_id": request_id}
    message.update(payload)
    sock.sendall((json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8"))
    received = bytearray()
    while b"\n" not in received:
        data = sock.recv(4096)
        if not data:
            raise AssertionError("controller closed the connection before replying")
        received.extend(data)
    line, _, _ = received.partition(b"\n")
    return json.loads(line.decode("utf-8"))


def _expect(label, response, **expected):
    # type: (str, Dict[str, Any], Any) -> None
    for field, value in expected.items():
        if response.get(field) != value:
            raise AssertionError("{0}: expected {1}={2!r}, got {3!r}".format(label, field, value, response))


def run_smoke(host, port, timeout=3.0):
    # type: (str, int, float) -> List[Tuple[str, Dict[str, Any]]]
    results = []  # type: List[Tuple[str, Dict[str, Any]]]
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        response = _request(sock, "smoke-heartbeat-1", "heartbeat")
        _expect("heartbeat", response, type="ack", status="alive")
        results.append(("heartbeat", response))

        response = _request(sock, "smoke-state-1", "pipeline_state")
        _expect("pipeline_state", response, type="pipeline_state", state="idle")
        if response["pipeline_state"]["queue_length"] != 0:
            raise AssertionError("pipeline_state: expected an empty FIFO: {0!r}".format(response))
        results.append(("pipeline_state", response))

        for command_id, shape in ((101, "triangle"), (102, "circle"), (103, "rectangle")):
            response = _request(sock, "smoke-enqueue-{0}".format(command_id), "enqueue", command_id=command_id, shape=shape)
            _expect("enqueue {0}".format(shape), response, type="ack", status="accepted", command_id=command_id)
            results.append(("enqueue {0}".format(shape), response))

        response = _request(sock, "smoke-full", "enqueue", command_id=104, shape="triangle")
        _expect("FIFO full", response, type="ack", status="queue_full", command_id=104)
        results.append(("FIFO full", response))

        response = _request(sock, "smoke-duplicate", "enqueue", command_id=101, shape="triangle")
        _expect("duplicate command_id", response, type="ack", status="duplicate", command_id=101)
        results.append(("duplicate command_id", response))

        response = _request(sock, "smoke-reset", "reset")
        _expect("reset", response, type="ack", status="reset")
        if not response["pipeline_state"]["empty"]:
            raise AssertionError("reset: FIFO was not empty: {0!r}".format(response))
        results.append(("reset", response))

        for command_id, shape in ((201, "triangle"), (202, "circle")):
            response = _request(sock, "smoke-order-enqueue-{0}".format(command_id), "enqueue", command_id=command_id, shape=shape)
            _expect("FIFO order enqueue {0}".format(shape), response, type="ack", status="accepted", command_id=command_id)

        response = _request(sock, "smoke-order-key1-triangle", "key_event", key="KEY1")
        _expect("FIFO order triangle", response, type="sorted", branch="Branch1")
        if response["command"]["command_id"] != 201 or response["pipeline_state"]["front"]["command_id"] != 202:
            raise AssertionError("FIFO order: triangle did not leave circle at the front: {0!r}".format(response))

        response = _request(sock, "smoke-order-key1-circle", "key_event", key="KEY1")
        _expect("FIFO order circle station 1", response, type="pipeline_state", status="moved", state="Station2")
        response = _request(sock, "smoke-order-key2-circle", "key_event", key="KEY2")
        _expect("FIFO order circle", response, type="sorted", branch="Branch2")
        if response["command"]["command_id"] != 202 or not response["pipeline_state"]["empty"]:
            raise AssertionError("FIFO order: circle was not sorted second: {0!r}".format(response))
        results.append(("FIFO order via key_event protocol", response))

    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        response = _request(sock, "smoke-reconnect", "heartbeat")
        _expect("reconnect", response, type="ack", status="alive")
        results.append(("reconnect", response))
    return results


def main():
    # type: () -> int
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--timeout", type=float, default=3.0)
    args = parser.parse_args()
    try:
        results = run_smoke(args.host, args.port, args.timeout)
    except (AssertionError, OSError, ValueError, json.JSONDecodeError) as error:
        print("SMOKE FAIL: {0}".format(error), file=sys.stderr)
        return 1
    for label, response in results:
        print("PASS {0}: {1}".format(label, json.dumps(response, sort_keys=True, ensure_ascii=False)))
    print("SMOKE PASS: {0} checks".format(len(results)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
