"""GUI 复用小组件：卡片容器与任务队列行。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Tuple

from . import theme
from .task_catalog import TaskSettings, TaskSpec


def make_card(
    parent: tk.Misc, title: str, subtitle: str = ""
) -> Tuple[tk.Frame, tk.Frame, tk.Frame]:
    """白底带边框的卡片，返回 (外框, 标题栏, 内容区)。"""
    outer = tk.Frame(
        parent,
        bg=theme.SURFACE,
        highlightbackground=theme.BORDER,
        highlightthickness=1,
    )
    header = tk.Frame(outer, bg=theme.SURFACE)
    header.pack(fill=tk.X, padx=14, pady=(10, 6))
    tk.Label(
        header, text=title, bg=theme.SURFACE, fg=theme.TEXT, font=theme.FONT_SECTION
    ).pack(side=tk.LEFT)
    if subtitle:
        tk.Label(
            header,
            text=subtitle,
            bg=theme.SURFACE,
            fg=theme.MUTED,
            font=theme.FONT_UI,
        ).pack(side=tk.LEFT, padx=(8, 0))
    body = tk.Frame(outer, bg=theme.SURFACE)
    body.pack(fill=tk.BOTH, expand=True)
    return outer, header, body


def describe_settings(spec: TaskSpec, settings: TaskSettings) -> str:
    """把任务参数压缩成一行，例如 ``2 次 × 35 分钟``。"""
    count = settings.value(spec, "count", None)
    minutes = settings.value(spec, "minutes", None)
    if minutes is None:
        minutes = settings.value(spec, "duration_minutes", None)
    parts: List[str] = []
    if minutes is not None:
        text = f"{float(minutes):g} 分钟"
        if count is not None and int(count) > 1:
            text = f"{int(count)} 次 × {text}"
        parts.append(text)
    elif count is not None and int(count) > 1:
        parts.append(f"{int(count)} 次")
    timeout = settings.value(spec, "timeout_minutes", None)
    if timeout is not None:
        parts.append(f"超时 {float(timeout):g} 分钟")
    title = str(settings.value(spec, "book_title", "") or "").strip()
    if title:
        parts.append(f"《{title}》")
    if str(settings.value(spec, "cover_image", "") or "").strip():
        parts.append("封面")
    return " · ".join(parts) or "无参数"


class TaskRow(tk.Frame):
    """任务队列中的一行：勾选 + 序号 + 名称 + 参数摘要 + 上下移动。"""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        spec: TaskSpec,
        index: int,
        enabled_var: tk.BooleanVar,
        on_toggle: Callable[[], None],
        on_select: Callable[[], None],
        on_move: Callable[[int], None],
    ) -> None:
        super().__init__(parent, bg=theme.SURFACE, cursor="hand2")
        self.spec = spec
        self._selected = False
        self._bg_widgets: List[tk.Widget] = [self]

        self._accent = tk.Frame(self, bg=theme.SURFACE, width=3)
        self._accent.pack(side=tk.LEFT, fill=tk.Y)

        badge = tk.Label(
            self,
            text=f"{index:02d}",
            bg=theme.ACCENT_SOFT,
            fg=theme.ACCENT_ACTIVE,
            width=3,
            font=("Consolas", 9, "bold"),
        )
        badge.pack(side=tk.LEFT, padx=(8, 6), pady=8)

        self._check = tk.Checkbutton(
            self,
            variable=enabled_var,
            command=on_toggle,
            bg=theme.SURFACE,
            activebackground=theme.SURFACE,
            selectcolor=theme.SURFACE,
            bd=0,
            highlightthickness=0,
        )
        self._check.pack(side=tk.LEFT)
        self._bg_widgets.append(self._check)

        # 先放右侧移动按钮，保证窄宽度下按钮不被名称挤掉
        moves = tk.Frame(self, bg=theme.SURFACE)
        moves.pack(side=tk.RIGHT, padx=(0, 6))
        self._bg_widgets.append(moves)
        for text_, direction in (("▲", -1), ("▼", 1)):
            arrow = tk.Label(
                moves,
                text=text_,
                bg=theme.SURFACE,
                fg=theme.SUBTLE,
                font=theme.FONT_UI,
                padx=4,
                cursor="hand2",
            )
            arrow.pack(side=tk.LEFT)
            arrow.bind("<Button-1>", lambda _event, d=direction: on_move(d))
            arrow.bind("<Enter>", lambda _event, w=arrow: w.configure(fg=theme.ACCENT))
            arrow.bind("<Leave>", lambda _event, w=arrow: w.configure(fg=theme.SUBTLE))
            self._bg_widgets.append(arrow)

        text = tk.Frame(self, bg=theme.SURFACE)
        text.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 4), pady=5)
        self._bg_widgets.append(text)
        title = tk.Frame(text, bg=theme.SURFACE)
        title.pack(fill=tk.X)
        self._bg_widgets.append(title)
        name = tk.Label(
            title,
            text=spec.name,
            bg=theme.SURFACE,
            fg=theme.TEXT,
            font=theme.FONT_BOLD,
            anchor="w",
        )
        name.pack(side=tk.LEFT)
        self._bg_widgets.append(name)
        if not spec.default_enabled:
            tag = tk.Label(
                title,
                text="可选",
                bg="#f2f4f7",
                fg=theme.MUTED,
                font=theme.FONT_SMALL,
                padx=5,
            )
            tag.pack(side=tk.LEFT, padx=(6, 0))
        self.meta_var = tk.StringVar()
        meta = tk.Label(
            text,
            textvariable=self.meta_var,
            bg=theme.SURFACE,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
            anchor="w",
        )
        meta.pack(fill=tk.X)
        self._bg_widgets.append(meta)

        for widget in (self, badge, text, title, name, meta):
            widget.bind("<Button-1>", lambda _event: on_select())

    def set_meta(self, text: str) -> None:
        self.meta_var.set(text)

    def set_selected(self, selected: bool) -> None:
        if selected == self._selected:
            return
        self._selected = selected
        bg = theme.SELECTED if selected else theme.SURFACE
        for widget in self._bg_widgets:
            widget.configure(bg=bg)
        self._check.configure(activebackground=bg, selectcolor=bg)
        self._accent.configure(bg=theme.ACCENT if selected else theme.SURFACE)
