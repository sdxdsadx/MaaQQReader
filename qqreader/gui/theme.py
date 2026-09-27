"""GUI 配色、字体与 ttk 样式（集中管理，避免散落在布局代码中）。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

BG = "#f4f6fb"
SURFACE = "#ffffff"
SURFACE_ALT = "#f8f9fd"
SIDEBAR = "#1f2437"
SIDEBAR_MUTED = "#9aa3bd"
TEXT = "#172033"
MUTED = "#667085"
SUBTLE = "#98a2b3"
ACCENT = "#5b5bd6"
ACCENT_ACTIVE = "#4848bd"
ACCENT_SOFT = "#eeeeff"
SELECTED = "#e8e8ff"
DANGER = "#dc2626"
SUCCESS = "#16a34a"
WARNING = "#d97706"
BORDER = "#e3e8f2"
LOG_BG = "#111827"
LOG_FG = "#e2e8f0"

FONT_FAMILY = "Microsoft YaHei UI"
FONT_UI = (FONT_FAMILY, 9)
FONT_SMALL = (FONT_FAMILY, 8)
FONT_BOLD = (FONT_FAMILY, 9, "bold")
FONT_SECTION = (FONT_FAMILY, 11, "bold")
FONT_HEADING = (FONT_FAMILY, 14, "bold")
FONT_TITLE = (FONT_FAMILY, 16, "bold")
FONT_MONO = ("Consolas", 9)

# 串行步骤状态 → (图标, 文字, 颜色)
STEP_STYLES = {
    "WAITING": ("○", "等待", SUBTLE),
    "RUNNING": ("▶", "运行中", ACCENT),
    "SUCCEEDED": ("✓", "成功", SUCCESS),
    "FAILED": ("✗", "失败", DANGER),
    "BLOCKED_BY_CAPTCHA": ("⚠", "验证码阻塞", WARNING),
    "CANCELLED": ("■", "已取消", WARNING),
    "SKIPPED": ("–", "跳过", SUBTLE),
}

# 日志行着色
LOG_TAGS = {
    "info": LOG_FG,
    "observe": "#7dd3fc",
    "success": "#4ade80",
    "error": "#f87171",
    "warn": "#fbbf24",
}


def status_color(text: str) -> str:
    """根据状态文字挑选状态点颜色。"""
    if any(token in text for token in ("失败", "错误")):
        return DANGER
    if "停止" in text:
        return WARNING
    if any(token in text for token in ("运行中", "启动", "读取", "等待")):
        return ACCENT
    if any(token in text for token in ("完成", "成功")):
        return SUCCESS
    return MUTED


def log_tag(message: str) -> str:
    """根据日志内容挑选着色标签。"""
    if "[observe" in message:
        return "observe"
    if any(token in message for token in ("失败", "错误", "[ERR]", "[not-implemented]")):
        return "error"
    if "未接入" in message or "旧流程" in message:
        return "warn"
    if any(token in message for token in ("成功", "完成")):
        return "success"
    return "info"


def configure_styles(root: tk.Misc) -> ttk.Style:
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    style.configure(".", font=FONT_UI, background=BG, foreground=TEXT)
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=TEXT)

    style.configure(
        "Toolbar.TButton",
        padding=(10, 6),
        borderwidth=0,
        background=SURFACE,
        foreground=TEXT,
    )
    style.map("Toolbar.TButton", background=[("active", "#eef1f7")])
    style.configure(
        "Icon.TButton",
        padding=(4, 2),
        borderwidth=0,
        background=SURFACE,
        foreground=MUTED,
    )
    style.map("Icon.TButton", background=[("active", ACCENT_SOFT)])
    style.configure(
        "Soft.TButton",
        padding=(14, 9),
        foreground=ACCENT_ACTIVE,
        background=ACCENT_SOFT,
        borderwidth=0,
        font=(FONT_FAMILY, 10, "bold"),
    )
    style.map(
        "Soft.TButton",
        background=[("active", "#dedefe"), ("disabled", "#f2f4f7")],
        foreground=[("disabled", SUBTLE)],
    )
    style.configure(
        "Primary.TButton",
        font=(FONT_FAMILY, 10, "bold"),
        foreground="#ffffff",
        background=ACCENT,
        padding=(20, 9),
        borderwidth=0,
    )
    style.map(
        "Primary.TButton",
        background=[("active", ACCENT_ACTIVE), ("disabled", "#b4b4ee")],
        foreground=[("disabled", "#ffffff")],
    )
    style.configure(
        "Danger.TButton",
        font=(FONT_FAMILY, 10, "bold"),
        foreground="#ffffff",
        background=DANGER,
        padding=(16, 9),
        borderwidth=0,
    )
    style.map(
        "Danger.TButton",
        background=[("active", "#b91c1c"), ("disabled", "#fca5a5")],
    )
    style.configure(
        "Nav.TButton",
        padding=(12, 8),
        borderwidth=0,
        background=SIDEBAR,
        foreground="#e4e7f2",
        anchor="w",
    )
    style.map(
        "Nav.TButton",
        background=[("active", "#2d3350"), ("disabled", SIDEBAR)],
        foreground=[("disabled", "#5d6580")],
    )

    style.configure(
        "Steps.Treeview",
        rowheight=26,
        font=FONT_UI,
        background=SURFACE,
        fieldbackground=SURFACE,
        foreground=TEXT,
        borderwidth=0,
    )
    style.configure(
        "Steps.Treeview.Heading",
        font=FONT_BOLD,
        background=SURFACE_ALT,
        foreground=MUTED,
        relief="flat",
    )
    style.map(
        "Steps.Treeview",
        background=[("selected", SELECTED)],
        foreground=[("selected", TEXT)],
    )
    style.configure(
        "Run.Horizontal.TProgressbar",
        troughcolor="#e6e9f2",
        background=ACCENT,
        borderwidth=0,
        thickness=8,
    )
    return style
