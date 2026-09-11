"""Enumerate configured cameras or use an explicit, audited device path."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
from cv2_enumerate_cameras import enumerate_cameras


BACKENDS = {
    "ANY": cv2.CAP_ANY,
    "DSHOW": cv2.CAP_DSHOW,
    "MSMF": cv2.CAP_MSMF,
    "V4L2": cv2.CAP_V4L2,
}


@dataclass(frozen=True)
class CameraDevice:
    index: int | str
    name: str
    path: str
    vid: int | None
    pid: int | None
    backend_name: str
    backend_id: int


def resolve_backend(name: str) -> int:
    """Resolve a supported backend name to its OpenCV numeric constant."""

    normalized = name.strip().upper()
    try:
        return BACKENDS[normalized]
    except KeyError as error:
        supported = ", ".join(sorted(BACKENDS))
        raise ValueError(f"unsupported backend {name!r}; choose one of: {supported}") from error


def enumerate_camera_devices(backend_name: str) -> list[CameraDevice]:
    """Return cameras visible to the selected OpenCV backend."""

    backend_id = resolve_backend(backend_name)
    devices: list[CameraDevice] = []
    for info in enumerate_cameras(backend_id):
        devices.append(
            CameraDevice(
                index=info.index,
                name=info.name,
                path=info.path,
                vid=info.vid,
                pid=info.pid,
                backend_name=backend_name.strip().upper(),
                backend_id=backend_id,
            )
        )
    return devices


def select_camera_device(
    devices: list[CameraDevice],
    preferred_name: str,
    fallback_index: int | None,
) -> CameraDevice:
    """Select by case-insensitive name first, then by configured fallback index."""

    name_fragment = preferred_name.strip().casefold()
    if name_fragment:
        matching = [device for device in devices if name_fragment in device.name.casefold()]
        if len(matching) == 1:
            return matching[0]
        if len(matching) > 1:
            exact = [device for device in matching if device.name.casefold() == name_fragment]
            if len(exact) == 1:
                return exact[0]
            names = ", ".join(device.name for device in matching)
            raise RuntimeError(f"camera name {preferred_name!r} is ambiguous: {names}")

    if fallback_index is not None:
        for device in devices:
            if device.index == fallback_index:
                return device

    available = ", ".join(f"{device.index}:{device.name}" for device in devices) or "none"
    raise RuntimeError(
        f"preferred camera {preferred_name!r} was not found and fallback index "
        f"{fallback_index!r} is unavailable; detected cameras: {available}"
    )
