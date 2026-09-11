"""Root-owned helper that can write only the three approved Linux LED classes."""

from __future__ import annotations

import argparse
import grp
import json
import os
import select
import socket
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

from device.imx6ull.core.models import BranchOutputEvent, OutputEvent, OutputOffEvent

from .protocol import MAX_OUTPUT_MESSAGE_BYTES, OutputProtocolError, decode_output_event


LED_NAMES = ("red", "green", "blue")
LED_ON_BRIGHTNESS = 255


@dataclass(frozen=True)
class LedHelperConfig:
    socket_path: Path
    socket_mode: int
    socket_group: str
    duration_ms: int

    @classmethod
    def from_dict(cls, value: object) -> "LedHelperConfig":
        if not isinstance(value, dict):
            raise ValueError("LED helper config must be an object")
        socket_path = value.get("socket_path")
        socket_mode = value.get("socket_mode")
        socket_group = value.get("socket_group")
        duration_ms = value.get("duration_ms")
        if not isinstance(socket_path, str) or not socket_path.startswith("/"):
            raise ValueError("socket_path must be an absolute path")
        if not isinstance(socket_mode, str):
            raise ValueError("socket_mode must be an octal string")
        try:
            parsed_mode = int(socket_mode, 8)
        except ValueError as error:
            raise ValueError("socket_mode must be an octal string") from error
        if parsed_mode & ~0o777 or parsed_mode & 0o007:
            raise ValueError("socket_mode must not grant access to other users")
        if not isinstance(socket_group, str) or not socket_group:
            raise ValueError("socket_group must be a non-empty group name")
        if type(duration_ms) is not int or not 1 <= duration_ms <= 60000:
            raise ValueError("duration_ms must be an integer in [1, 60000]")
        return cls(Path(socket_path), parsed_mode, socket_group, duration_ms)


def load_led_helper_config(path: Path) -> LedHelperConfig:
    return LedHelperConfig.from_dict(json.loads(path.read_text(encoding="utf-8")))


class LedClassWriter:
    """The helper's fixed capability: only red, green and blue brightness files."""

    _BRANCH_LEDS = {
        "Branch1": frozenset({"red"}),
        "Branch2": frozenset({"red", "green"}),
        "Branch3": frozenset({"red", "green", "blue"}),
    }

    def __init__(self, led_root: Path = Path("/sys/class/leds")) -> None:
        self._brightness_paths = {
            name: led_root / name / "brightness" for name in LED_NAMES
        }  # type: Dict[str, Path]

    def display_branch(self, branch: str) -> None:
        enabled = self._BRANCH_LEDS.get(branch)
        if enabled is None:
            raise ValueError("unknown branch")
        self._write(enabled)

    def off(self) -> None:
        self._write(frozenset())

    def _write(self, enabled: frozenset) -> None:
        for name in LED_NAMES:
            value = LED_ON_BRIGHTNESS if name in enabled else 0
            self._brightness_paths[name].write_text(str(value), encoding="ascii")


class LedHelper:
    """Serve strict branch/off requests and own the one-second output timer."""

    def __init__(
        self,
        writer: LedClassWriter,
        duration_ms: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if duration_ms <= 0:
            raise ValueError("duration_ms must be positive")
        self.writer = writer
        self.duration_seconds = duration_ms / 1000.0
        self._clock = clock
        self._deadline = None  # type: Optional[float]
        self._listener = None  # type: Optional[socket.socket]
        self._socket_path = None  # type: Optional[Path]
        self.last_event = None  # type: Optional[OutputEvent]

    def handle_event(self, event: OutputEvent) -> None:
        if isinstance(event, BranchOutputEvent):
            self.writer.display_branch(event.branch)
            self._deadline = self._clock() + self.duration_seconds
        elif isinstance(event, OutputOffEvent):
            self.writer.off()
            self._deadline = None
        else:
            raise TypeError("unknown output event")
        self.last_event = event

    def tick(self) -> bool:
        if self._deadline is not None and self._clock() >= self._deadline:
            self.writer.off()
            self._deadline = None
            return True
        return False

    def start_socket(self, config: LedHelperConfig) -> None:
        path = config.socket_path
        parent = path.parent
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise RuntimeError("helper socket parent must be a real directory")
        parent.mkdir(mode=0o750, parents=True, exist_ok=True)
        # The Controller's service account needs search permission on this
        # directory, but no write permission.  The socket itself carries the
        # group read/write permission check.
        os.chmod(str(parent), 0o750)
        os.chown(str(parent), -1, grp.getgrnam(config.socket_group).gr_gid)
        if path.exists() or path.is_symlink():
            mode = path.lstat().st_mode
            if not stat.S_ISSOCK(mode):
                raise RuntimeError("refusing to replace a non-socket path")
            path.unlink()
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            listener.bind(str(path))
            os.chmod(str(path), config.socket_mode)
            os.chown(str(path), -1, grp.getgrnam(config.socket_group).gr_gid)
            listener.listen(8)
            listener.setblocking(False)
        except Exception:
            listener.close()
            raise
        self._listener = listener
        self._socket_path = path

    def serve_once(self, timeout: Optional[float] = None) -> bool:
        listener = self._listener
        if listener is None:
            raise RuntimeError("helper socket is not started")
        ready, _, _ = select.select([listener], [], [], timeout)
        if not ready:
            self.tick()
            return False
        connection, _ = listener.accept()
        try:
            raw = self._read_message(connection)
            self.handle_event(decode_output_event(raw))
        except (OSError, OutputProtocolError):
            # An invalid/unavailable unprivileged client must not expand this
            # root helper's ability or change the active LED state.
            pass
        finally:
            connection.close()
        self.tick()
        return True

    def serve_forever(self) -> None:
        while True:
            timeout = self._timeout_to_deadline()
            self.serve_once(timeout)

    def close(self) -> None:
        self._deadline = None
        self.writer.off()
        listener = self._listener
        self._listener = None
        if listener is not None:
            listener.close()
        path = self._socket_path
        self._socket_path = None
        if path is not None and path.exists() and stat.S_ISSOCK(path.lstat().st_mode):
            path.unlink()

    def _timeout_to_deadline(self) -> Optional[float]:
        if self._deadline is None:
            return None
        return max(0.0, self._deadline - self._clock())

    @staticmethod
    def _read_message(connection: socket.socket) -> bytes:
        connection.settimeout(0.2)
        received = bytearray()
        while b"\n" not in received and len(received) <= MAX_OUTPUT_MESSAGE_BYTES:
            chunk = connection.recv(MAX_OUTPUT_MESSAGE_BYTES + 1 - len(received))
            if not chunk:
                break
            received.extend(chunk)
        if len(received) > MAX_OUTPUT_MESSAGE_BYTES or received.count(b"\n") != 1 or not received.endswith(b"\n"):
            raise OutputProtocolError("invalid output message framing")
        return bytes(received)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = load_led_helper_config(args.config)
    helper = LedHelper(LedClassWriter(), config.duration_ms)
    # A restarted helper must never preserve an old actuator indication.
    helper.writer.off()
    helper.start_socket(config)
    try:
        helper.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        helper.close()


if __name__ == "__main__":
    raise SystemExit(main())
