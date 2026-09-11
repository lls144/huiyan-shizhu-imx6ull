"""Small, strict Unix-socket protocol between Controller and LED helper."""

from __future__ import annotations

import json
from typing import Any, Dict

from device.imx6ull.core.models import BRANCHES, BranchOutputEvent, OutputEvent, OutputOffEvent


OUTPUT_PROTOCOL_VERSION = 1
MAX_OUTPUT_MESSAGE_BYTES = 256


class OutputProtocolError(ValueError):
    """The root-owned helper rejects malformed or capability-expanding input."""


def encode_output_event(event: OutputEvent) -> bytes:
    if isinstance(event, BranchOutputEvent):
        payload = {"version": OUTPUT_PROTOCOL_VERSION, "type": "branch", "branch": event.branch}
    elif isinstance(event, OutputOffEvent):
        payload = {"version": OUTPUT_PROTOCOL_VERSION, "type": "off"}
    else:
        raise TypeError("event must be a BranchOutputEvent or OutputOffEvent")
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\n"
    if len(encoded) > MAX_OUTPUT_MESSAGE_BYTES:
        raise OutputProtocolError("output message exceeds maximum size")
    return encoded


def decode_output_event(raw: bytes) -> OutputEvent:
    if not isinstance(raw, bytes) or not raw.endswith(b"\n"):
        raise OutputProtocolError("output message must be one newline-terminated byte string")
    if len(raw) > MAX_OUTPUT_MESSAGE_BYTES:
        raise OutputProtocolError("output message exceeds maximum size")
    try:
        value = json.loads(raw[:-1].decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise OutputProtocolError("output message is not valid UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise OutputProtocolError("output message must be an object")
    _validate_message(value)
    if value["type"] == "off":
        return OutputOffEvent()
    return BranchOutputEvent(value["branch"])


def _validate_message(value: Dict[str, Any]) -> None:
    if type(value.get("version")) is not int or value["version"] != OUTPUT_PROTOCOL_VERSION:
        raise OutputProtocolError("unsupported output protocol version")
    message_type = value.get("type")
    if message_type == "off":
        if set(value) != {"version", "type"}:
            raise OutputProtocolError("off message has unsupported fields")
        return
    if message_type == "branch":
        if set(value) != {"version", "type", "branch"}:
            raise OutputProtocolError("branch message has unsupported fields")
        if value.get("branch") not in BRANCHES:
            raise OutputProtocolError("branch message has invalid branch")
        return
    raise OutputProtocolError("unsupported output message type")
