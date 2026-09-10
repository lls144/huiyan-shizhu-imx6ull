"""Small dependency-free representation of the M7 JSON Lines protocol."""

from __future__ import annotations

import json
from typing import Any

PROTOCOL_VERSION = 1
SHAPES = frozenset({"triangle", "rectangle", "circle"})
REQUEST_TYPES = frozenset({"enqueue", "heartbeat", "pipeline_state", "reset"})
MAX_LINE_BYTES = 16 * 1024


class ProtocolError(ValueError):
    """A peer-visible validation failure with a stable protocol error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def encode_line(message: dict[str, Any]) -> bytes:
    """Encode one compact UTF-8 JSON object followed by exactly one LF."""

    return (json.dumps(message, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def decode_line(line: bytes) -> dict[str, Any]:
    try:
        value = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolError("MALFORMED_JSON", "message must be a UTF-8 JSON object") from error
    if not isinstance(value, dict):
        raise ProtocolError("INVALID_MESSAGE", "message root must be an object")
    return value


def request_id_from(message: object) -> str | None:
    return message.get("request_id") if isinstance(message, dict) and isinstance(message.get("request_id"), str) else None


def _positive_int(value: object, field: str) -> int:
    if type(value) is not int or value <= 0:
        raise ProtocolError("INVALID_MESSAGE", f"{field} must be a positive integer")
    return value


def validate_request(message: dict[str, Any]) -> None:
    """Validate the request forms accepted by the Desktop controller server."""

    if type(message.get("version")) is not int:
        raise ProtocolError("INVALID_MESSAGE", "version must be an integer")
    if message["version"] != PROTOCOL_VERSION:
        raise ProtocolError("UNSUPPORTED_VERSION", f"version must be {PROTOCOL_VERSION}")
    message_type = message.get("type")
    if not isinstance(message_type, str):
        raise ProtocolError("INVALID_MESSAGE", "type must be a string")
    if message_type not in REQUEST_TYPES:
        raise ProtocolError("UNKNOWN_TYPE", f"unsupported message type: {message_type}")
    request_id = message.get("request_id")
    if not isinstance(request_id, str) or not request_id:
        raise ProtocolError("INVALID_MESSAGE", "request_id must be a non-empty string")
    if message_type == "enqueue":
        _positive_int(message.get("command_id"), "command_id")
        shape = message.get("shape")
        if shape not in SHAPES:
            raise ProtocolError("INVALID_SHAPE", "shape must be triangle, rectangle, or circle")
        for field in ("source_event_id", "source_object_id"):
            if field in message:
                _positive_int(message[field], field)


def error_message(code: str, message: str, request_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": PROTOCOL_VERSION,
        "type": "error",
        "code": code,
        "message": message,
    }
    if request_id is not None:
        payload["request_id"] = request_id
    return payload
