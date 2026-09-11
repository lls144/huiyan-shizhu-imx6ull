"""Static checks for the M10 linuxfb/tslib launcher and service template."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class HmiLaunchAssetTests(unittest.TestCase):
    def test_launcher_uses_verified_linuxfb_tslib_stack_and_single_instance_lock(self):
        source = (ROOT / "scripts" / "start_hmi.sh").read_text(encoding="utf-8")
        for required in (
            "linuxfb:fb=/dev/fb0",
            "QT_QPA_PLATFORM_PLUGIN_PATH=/usr/lib/plugins",
            "QT_QPA_FONTDIR=/usr/lib/fonts",
            "TSLIB_TSDEVICE",
            "QT_QPA_GENERIC_PLUGINS",
            "QT_QPA_FB_TSLIB=1",
            "QT_QPA_EGLFS_TSLIB=1",
            "QWS_MOUSE_PROTO=tslib",
            "Goodix Capacitive TouchScreen",
            "goodix-ts",
            "iMX6UL Touchscreen Controller",
            "flock -n 9",
            "ps -u \"$UID\" -o pid= -o args=",
            "exec /usr/bin/python3 -m device.imx6ull.hmi.app",
        ):
            self.assertIn(required, source)
        lines = source.splitlines()
        self.assertTrue(any(line.startswith("unset ") and "QT_QPA_FB_HIDECURSOR" in line for line in lines))
        self.assertFalse(any(line.strip().startswith("export QT_QPA_FB_HIDECURSOR=1") for line in lines))

    def test_hmi_service_is_unprivileged_and_uses_launcher(self):
        source = (ROOT / "systemd" / "huiyan-hmi.service").read_text(encoding="utf-8")
        self.assertIn("User=debian", source)
        self.assertIn("SupplementaryGroups=input", source)
        self.assertIn("WorkingDirectory=/home/debian/huiyan-shizhu", source)
        self.assertIn("ExecStart=/home/debian/huiyan-shizhu/device/imx6ull/scripts/start_hmi.sh", source)
        self.assertIn("Restart=on-failure", source)
        self.assertIn("WantedBy=graphical.target", source)
