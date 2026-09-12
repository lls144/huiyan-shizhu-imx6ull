"""Create the multi-resolution Windows icon from the committed SVG source."""

from __future__ import annotations

import io
import sys
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QSize
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


SIZES = (16, 24, 32, 48, 64, 128, 256)


def _png_bytes(svg: bytes, size: int) -> bytes:
    image = QImage(QSize(size, size), QImage.Format.Format_ARGB32)
    image.fill(0)
    renderer = QSvgRenderer(svg)
    if not renderer.isValid():
        raise RuntimeError("invalid SVG icon source")
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise RuntimeError(f"could not render {size}px PNG")
    return bytes(buffer.data())


def main(argv: list[str] | None = None) -> int:
    parser_args = list(argv or sys.argv[1:])
    if len(parser_args) != 2:
        raise SystemExit("usage: build_icon.py SOURCE.svg OUTPUT.ico")
    source, output = (Path(value).resolve() for value in parser_args)
    svg = source.read_bytes()
    images = [Image.open(io.BytesIO(_png_bytes(svg, size))).copy() for size in SIZES]
    output.parent.mkdir(parents=True, exist_ok=True)
    images[-1].save(
        output,
        format="ICO",
        sizes=[(size, size) for size in SIZES],
        append_images=images[:-1],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
