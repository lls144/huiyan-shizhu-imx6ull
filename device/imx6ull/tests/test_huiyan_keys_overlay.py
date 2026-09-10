"""Static safety checks for the i.MX6ULL gpio-keys overlay source."""

from __future__ import annotations

import unittest
from pathlib import Path


OVERLAY_DIR = Path(__file__).parents[1] / "overlay"


class HuiyanKeysOverlayTests(unittest.TestCase):
    def test_overlay_uses_only_the_three_verified_gpio1_pads(self) -> None:
        source = (OVERLAY_DIR / "huiyan-keys.dts").read_text(encoding="utf-8")
        self.assertIn("&gpio1 24 GPIO_ACTIVE_LOW", source)
        self.assertIn("&gpio1 25 GPIO_ACTIVE_LOW", source)
        self.assertIn("&gpio1 26 GPIO_ACTIVE_LOW", source)
        self.assertNotIn("gpio2", source)
        self.assertNotIn("GPIO2_IO", source)
        self.assertNotIn("GPIO1_IO11", source)
        self.assertNotIn("GPIO1_IO12", source)

    def test_overlay_declares_gpio_keys_pullups_and_debounce(self) -> None:
        source = (OVERLAY_DIR / "huiyan-keys.dts").read_text(encoding="utf-8")
        header = (OVERLAY_DIR / "huiyan-keys-pinfunc.h").read_text(encoding="utf-8")
        self.assertIn('compatible = "gpio-keys"', source)
        self.assertIn('label = "huiyan-keys"', source)
        self.assertEqual(source.count("debounce-interval = <20>;"), 3)
        self.assertIn("HUIYAN_PAD_CTL_INPUT_PULL_UP", source)
        self.assertIn("#define HUIYAN_PAD_CTL_INPUT_PULL_UP 0x0001b0b1", header)
        self.assertIn("MX6UL_PAD_UART3_TX_DATA__GPIO1_IO24", header)
        self.assertIn("MX6UL_PAD_UART3_RX_DATA__GPIO1_IO25", header)
        self.assertIn("MX6UL_PAD_UART3_CTS_B__GPIO1_IO26", header)
