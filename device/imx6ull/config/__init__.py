"""Validated controller configuration; no board-specific defaults are inferred."""

from .controller_config import ControllerConfig, GpioKeyConfig, load_controller_config

__all__ = ["ControllerConfig", "GpioKeyConfig", "load_controller_config"]
