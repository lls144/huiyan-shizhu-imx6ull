"""Central design tokens and QSS for the compact desktop vision workspace."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QFontDatabase


@dataclass(frozen=True)
class ThemeTokens:
    background: str = "#181818"
    editor: str = "#1e1e1e"
    sidebar: str = "#1b1b1b"
    toolbar: str = "#202020"
    elevated: str = "#252526"
    hover: str = "#2a2d2e"
    pressed: str = "#333333"
    divider: str = "#303030"
    text: str = "#d4d4d4"
    strong_text: str = "#f0f0f0"
    muted_text: str = "#969696"
    disabled_text: str = "#606060"
    accent: str = "#3f86d9"
    accent_hover: str = "#4b91e4"
    success: str = "#73c991"
    error: str = "#e07a7a"
    warning: str = "#d7ba7d"
    app_bar_height: int = 40
    workspace_bar_height: int = 34
    evidence_bar_height: int = 38
    status_bar_height: int = 24
    tool_height: int = 28
    sidebar_min_width: int = 300
    sidebar_max_width: int = 420
    base_spacing: int = 6


THEME = ThemeTokens()


@dataclass(frozen=True)
class OverlayTokens:
    roi_bgr: tuple[int, int, int] = (112, 112, 112)
    triangle_bgr: tuple[int, int, int] = (94, 197, 34)
    rectangle_bgr: tuple[int, int, int] = (246, 130, 59)
    circle_bgr: tuple[int, int, int] = (22, 115, 249)
    unknown_bgr: tuple[int, int, int] = (68, 68, 239)
    bbox_outline_bgr: tuple[int, int, int] = (24, 24, 24)
    roi_thickness: int = 1
    bbox_outline_thickness: int = 5
    bbox_thickness: int = 3
    font_scale: float = 0.62
    font_thickness: int = 2
    label_padding_x: int = 7
    label_padding_y: int = 5


OVERLAY = OverlayTokens()


def load_ui_fonts() -> None:
    """Make native Windows UI fonts available under Qt's offscreen platform."""

    windows_dir = os.environ.get("WINDIR")
    if not windows_dir:
        return
    font_dir = Path(windows_dir) / "Fonts"
    for name in ("segoeui.ttf", "segoeuib.ttf", "msyh.ttc", "msyhbd.ttc"):
        path = font_dir / name
        if path.exists():
            QFontDatabase.addApplicationFont(str(path))


def build_stylesheet(tokens: ThemeTokens = THEME) -> str:
    return f"""
QWidget {{
    color: {tokens.text};
    background: {tokens.background};
    font-family: "Segoe UI", "Microsoft YaHei UI";
    font-size: 12px;
}}
QMainWindow, QWidget#root {{ background: {tokens.background}; }}
QLabel {{ background: transparent; }}
QFrame#applicationBar {{
    background: {tokens.toolbar};
    border-bottom: 1px solid {tokens.divider};
}}
QLabel#appTitle {{ color: {tokens.strong_text}; font-size: 14px; font-weight: 600; }}
QLabel#appSubtitle, QLabel#sourceBadge {{
    color: {tokens.muted_text};
    font-size: 11px;
}}
QLabel#stateDot {{ font-size: 11px; color: {tokens.muted_text}; }}
QLabel#stateDot[state="running"] {{ color: {tokens.success}; }}
QLabel#stateDot[state="starting"], QLabel#stateDot[state="stopping"] {{ color: {tokens.warning}; }}
QLabel#stateDot[state="error"] {{ color: {tokens.error}; }}
QLabel#stateText {{ color: {tokens.text}; font-size: 11px; }}
QFrame#workspace {{ background: {tokens.editor}; }}
QFrame#workspaceToolbar, QFrame#evidenceToolbar {{
    background: {tokens.toolbar};
    border: none;
}}
QFrame#workspaceToolbar {{ border-bottom: 1px solid {tokens.divider}; }}
QFrame#evidenceToolbar {{ border-top: 1px solid {tokens.divider}; }}
QLabel#workspaceTitle {{ color: {tokens.text}; font-size: 11px; font-weight: 600; }}
QLabel#video {{
    background: {tokens.editor};
    border: none;
    color: {tokens.muted_text};
    font-size: 12px;
}}
QFrame#inspector {{
    background: {tokens.sidebar};
    border-left: 1px solid {tokens.divider};
}}
QLabel#inspectorTitle {{ color: {tokens.text}; font-size: 11px; font-weight: 600; }}
QLabel#sectionTitle {{
    color: {tokens.muted_text};
    font-size: 10px;
    font-weight: 600;
}}
QLabel#metadataKey {{ color: {tokens.muted_text}; font-size: 11px; }}
QLabel#metadataValue {{ color: {tokens.text}; font-size: 11px; }}
QLabel#errorValue {{ color: {tokens.muted_text}; font-size: 11px; }}
QLabel#errorValue[hasError="true"] {{ color: {tokens.error}; }}
QLabel#boardStateValue {{ color: {tokens.text}; font-size: 11px; font-family: "Consolas", "Microsoft YaHei UI"; }}
QLabel#boardStateValue[connection="online"] {{ color: {tokens.success}; }}
QLabel#boardStateValue[connection="connecting"] {{ color: {tokens.warning}; }}
QLabel#boardStateValue[connection="offline"] {{ color: {tokens.error}; }}
QLabel#boardStateValue[enqueueOutcome="accepted"] {{ color: {tokens.success}; }}
QLabel#boardStateValue[enqueueOutcome="failed"] {{ color: {tokens.error}; }}
QWidget#digitalSortingLine {{ border-top: 1px solid {tokens.divider}; }}
QFrame#divider {{ color: {tokens.divider}; background: {tokens.divider}; max-height: 1px; }}
QToolButton {{
    min-height: {tokens.tool_height}px;
    max-height: {tokens.tool_height}px;
    padding: 0 9px;
    color: {tokens.text};
    background: transparent;
    border: 1px solid transparent;
    border-radius: 3px;
}}
QToolButton:hover {{ background: {tokens.hover}; border-color: {tokens.divider}; }}
QToolButton:pressed {{ background: {tokens.pressed}; }}
QToolButton:disabled {{ color: {tokens.disabled_text}; background: transparent; border-color: transparent; }}
QToolButton#startTool {{ color: {tokens.strong_text}; background: {tokens.accent}; }}
QToolButton#startTool:hover {{ background: {tokens.accent_hover}; border-color: {tokens.accent_hover}; }}
QToolButton#evidenceTool {{ padding: 0 7px; color: {tokens.muted_text}; }}
QToolButton#evidenceTool:hover {{ color: {tokens.text}; }}
QListWidget {{
    background: transparent;
    border: none;
    outline: none;
    color: {tokens.text};
    font-family: "Consolas", "Microsoft YaHei UI";
    font-size: 11px;
}}
QListWidget::item {{ min-height: 24px; padding: 1px 3px; border: none; }}
QListWidget::item:hover {{ background: {tokens.hover}; }}
QListWidget::item:selected {{ background: {tokens.elevated}; color: {tokens.strong_text}; }}
QSplitter::handle {{ background: {tokens.divider}; width: 1px; }}
QStatusBar#statusBar {{
    min-height: {tokens.status_bar_height}px;
    max-height: {tokens.status_bar_height}px;
    color: {tokens.text};
    background: {tokens.toolbar};
    border: none;
    border-top: 1px solid {tokens.divider};
    font-size: 11px;
}}
QStatusBar#statusBar QLabel {{
    color: {tokens.muted_text};
    background: transparent;
    padding: 0 7px;
}}
QStatusBar#statusBar QLabel#statusItem {{ border-right: 1px solid {tokens.divider}; }}
QStatusBar#statusBar QLabel#statusSource {{ color: #8cb9ed; border-right: 1px solid {tokens.divider}; }}
QStatusBar#statusBar QLabel#statusState {{ color: {tokens.text}; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: #424242; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


APP_STYLE = build_stylesheet()
