#!/usr/bin/env python3
"""Capture EV_KEY events from an input device selected by its Linux name."""

from __future__ import print_function

import argparse
import json
import os
import select
import struct
import sys
import time
from pathlib import Path


EV_KEY = 0x01
INPUT_EVENT = struct.Struct("@llHHi")


def find_event_device(device_name, sys_class_input=Path("/sys/class/input")):
    """Return the /dev/input path for the uniquely named Linux input device."""

    matches = []
    for event_path in sorted(sys_class_input.glob("event*")):
        name_path = event_path / "device" / "name"
        try:
            name = name_path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if name == device_name:
            matches.append(Path("/dev/input") / event_path.name)
    if not matches:
        raise RuntimeError("input device not found: {0}".format(device_name))
    if len(matches) != 1:
        raise RuntimeError("input device name is ambiguous: {0}: {1}".format(device_name, matches))
    return matches[0]


def capture(device_path, duration):
    """Print JSON EV_KEY records until duration elapses; return their count."""

    descriptor = os.open(str(device_path), os.O_RDONLY | os.O_NONBLOCK)
    count = 0
    buffer = bytearray()
    deadline = time.monotonic() + duration
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return count
            readable, _, _ = select.select([descriptor], [], [], remaining)
            if not readable:
                return count
            buffer.extend(os.read(descriptor, INPUT_EVENT.size * 64))
            while len(buffer) >= INPUT_EVENT.size:
                raw = bytes(buffer[:INPUT_EVENT.size])
                del buffer[:INPUT_EVENT.size]
                seconds, microseconds, event_type, code, value = INPUT_EVENT.unpack(raw)
                if event_type != EV_KEY:
                    continue
                print(
                    json.dumps(
                        {
                            "code": code,
                            "device": str(device_path),
                            "seconds": seconds,
                            "microseconds": microseconds,
                            "type": "EV_KEY",
                            "value": value,
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
                count += 1
    finally:
        os.close(descriptor)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-name", default="huiyan-keys")
    parser.add_argument("--duration", type=float, default=20.0)
    args = parser.parse_args()
    if args.duration <= 0:
        parser.error("--duration must be positive")
    try:
        device_path = find_event_device(args.device_name)
        print(
            "LISTENING device_name={0} device={1} seconds={2}".format(
                args.device_name, device_path, args.duration
            ),
            flush=True,
        )
        count = capture(device_path, args.duration)
    except (OSError, RuntimeError) as error:
        print("CAPTURE FAIL: {0}".format(error), file=sys.stderr)
        return 1
    print("COMPLETE ev_key_count={0}".format(count), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
