"""Fixed-argument entry point for the Windows demonstration package."""

from __future__ import annotations

import sys

from pc.gui.app import main


if __name__ == "__main__":
    raise SystemExit(main(["--source", "camera", "--roi-mode", "fixed_normalized", *sys.argv[1:]]))
