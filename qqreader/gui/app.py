"""MAA GUI 风格控制台：任务树分级设置 + 串行执行。"""

from __future__ import annotations

import argparse
import os
import queue
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..config import AppConfig, ConfigError, load_config
from ..workflow import (
    DailyFlowRecorder,
    DailyFlowRun,
    FlowRunState,
    FlowStepState,
    snapshots_from_plans,
)
from .commands import (
    build_adb_connect_command,
    build_emulator_launch_command,
    build_run_task_command,
    command_preview,
)
from .task_catalog import (
    DEFAULT_TASK_CATALOG,
    TaskRunPlan,
    TaskSettings,
    TaskSpec,
    apply_daily_preset,
    apply_weekly_reading_preset,
    build_serial_plan,
    default_settings,
    load_task_order,
    load_task_settings,
    save_task_settings,
)


def _detect_repo_root() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
        for candidate in (base, *base.parents):
            if (candidate / "scripts" / "run_task.py").is_file():
                return candidate
        return base
    return Path(__file__).resolve().parents[2]


_REPO_ROOT = _detect_repo_root()

BG = "#f6f8fc"
CARD = "#ffffff"
TEXT = "#172033"
MUTED = "#667085"
ACCENT = "#5b5bd6"
ACCENT_ACTIVE = "#4848bd"
ACCENT_SOFT = "#eeeeff"
DANGER = "#dc2626"
SUCCESS = "#16a34a"
WARNING = "#d97706"
BORDER = "#e3e8f2"
LOG_BG = "#111827"
LOG_FG = "#e2e8f0"
FONT_UI = ("Microsoft YaHei UI", 9)
FONT_TITLE = ("Microsoft YaHei UI", 18, "bold")
FONT_MONO = ("Consolas", 9)


class QQReaderGui:
    """任务树 + 参数面板 + 串行执行的 GUI。"""

    def __init__(
        self,
        root: tk.Tk,
        *,
        repo_root: Optional[Path] = None,
        config_path: Optional[Path] = None,
    ) -> None:
        self.root = root
        self.repo_root = Path(repo_root or _REPO_ROOT)
        self._config: Optional[AppConfig] = None
        self._process: Optional[subprocess.Popen] = None
        self._busy = False
        self._stopping = False
        self._finish_callback: Optional[Callable[[int], None]] = None
        self._log_queue: "queue.Queue[str]" = queue.Queue()

        self._catalog: Sequence[TaskSpec] = DEFAULT_TASK_CATALOG
        self._ordered_catalog: List[TaskSpec] = list(self._catalog)
        self._settings: Dict[str, TaskSettings] = default_settings(self._catalog)
        self._selected_spec: Optional[TaskSpec] = None
        self._card_enabled_vars: Dict[str, tk.BooleanVar] = {}
        self._card_field_vars: Dict[str, Dict[str, tk.Variable]] = {}
        self._cards_container: Optional[tk.Frame] = None
        self._serial_plan: List[TaskRunPlan] = []
        self._serial_index = 0
        self._serial_run: Optional[DailyFlowRun] = None
        self._serial_recorder: Optional[DailyFlowRecorder] = None
        self._serial_record_path: Optional[Path] = None

        self._build_ui()
        self._load_task_settings_file()
        if config_path is not None:
            self._load_config(Path(config_path))

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        self.root.title("QQReader 每日任务控制台")
        self.root.geometry("1280x840")
        self.root.minsize(1080, 720)
        self.root.configure(bg=BG)
        self._configure_styles()
        self._build_header()
        self._build_toolbar()
        self._build_main_panes()
        self._build_action_bar()
        self.root.after(100, self._drain_log_queue)
        self._log(
            "GUI 已启动。日常使用只需点击「一键执行今日任务」；"
            "需要调试时可选择1分钟试跑或单独运行任务。"
        )

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", font=FONT_UI, background=BG, foreground=TEXT)
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Card.TLabel", background=CARD, foreground=TEXT)
        style.configure("Muted.TLabel", background=CARD, foreground=MUTED)
        style.configure("Title.TLabel", font=FONT_TITLE, background=BG, foreground=TEXT)
        style.configure(
            "CardHeader.TLabel",
            font=("Microsoft YaHei UI", 10, "bold"),
            background=CARD,
            foreground=TEXT,
        )
        style.configure("Toolbar.TButton", padding=(10, 7), borderwidth=0)
        style.configure(
            "Soft.TButton",
            padding=(12, 8),
            foreground=ACCENT_ACTIVE,
            background=ACCENT_SOFT,
            borderwidth=0,
        )
        style.map("Soft.TButton", background=[("active", "#dedefe")])
        style.configure(
            "Primary.TButton",
            font=("Microsoft YaHei UI", 11, "bold"),
            foreground="#ffffff",
            background=ACCENT,
            padding=(22, 11),
            borderwidth=0,
        )
        style.map(
            "Primary.TButton",
            background=[("active", ACCENT_ACTIVE), ("disabled", "#93c5fd")],
            foreground=[("disabled", "#ffffff")],
        )
        style.configure(
            "Danger.TButton",
            font=FONT_UI,
            foreground="#ffffff",
            background=DANGER,
            padding=(14, 7),
            borderwidth=0,
        )
        style.map(
            "Danger.TButton",
            background=[("active", "#b91c1c"), ("disabled", "#fca5a5")],
        )
        style.configure(
            "Treeview",
            rowheight=28,
            font=FONT_UI,
            background=CARD,
            fieldbackground=CARD,
            foreground=TEXT,
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            font=("Microsoft YaHei UI", 9, "bold"),
            background="#e8edf5",
            foreground=TEXT,
            relief="flat",
        )
        style.map(
            "Treeview",
            background=[("selected", "#dbeafe")],
            foreground=[("selected", TEXT)],
        )
        style.configure("TLabelframe", background=BG)
        style.configure(
            "TLabelframe.Label",
            background=BG,
            foreground=TEXT,
            font=("Microsoft YaHei UI", 9, "bold"),
        )

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=BG, padx=20, pady=14)
        header.pack(fill=tk.X)
        brand = tk.Frame(header, bg=BG)
        brand.pack(side=tk.LEFT)
        ttk.Label(brand, text="QQReader 自动任务", style="Title.TLabel").pack(
            anchor="w"
        )
        tk.Label(
            brand,
            text="一次配置，每日按顺序完成阅读、听书、游戏与广告",
            bg=BG,
            fg=MUTED,
            font=FONT_UI,
        ).pack(anchor="w", pady=(3, 0))

        right = tk.Frame(header, bg=BG)
        right.pack(side=tk.RIGHT)
        self._status_var = tk.StringVar(value="准备就绪")
        self._status_dot = tk.Label(
            right, text="●", bg=BG, fg=MUTED, font=("Segoe UI", 11)
        )
        self._status_dot.pack(side=tk.LEFT)
        tk.Label(
            right,
            textvariable=self._status_var,
            bg=BG,
            fg=TEXT,
            font=("Microsoft YaHei UI", 9, "bold"),
        ).pack(side=tk.LEFT, padx=(6, 0))

    def _build_toolbar(self) -> None:
        shell = tk.Frame(
            self.root,
            bg=CARD,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        shell.pack(fill=tk.X, padx=20, pady=(0, 12))
        bar = tk.Frame(shell, bg=CARD)
        bar.pack(fill=tk.X, padx=18, pady=(16, 12))
        self._action_buttons: List[ttk.Button] = []

        overview = tk.Frame(bar, bg=CARD)
        overview.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(
            overview,
            text="今天的任务",
            bg=CARD,
            fg=TEXT,
            font=("Microsoft YaHei UI", 12, "bold"),
        ).pack(anchor="w")
        self._selection_summary_var = tk.StringVar(value="正在读取任务设置…")
        tk.Label(
            overview,
            textvariable=self._selection_summary_var,
            bg=CARD,
            fg=ACCENT_ACTIVE,
            font=("Microsoft YaHei UI", 10, "bold"),
        ).pack(anchor="w", pady=(6, 0))
        self._selection_detail_var = tk.StringVar(value="")
        tk.Label(
            overview,
            textvariable=self._selection_detail_var,
            bg=CARD,
            fg=MUTED,
            font=FONT_UI,
            anchor="w",
        ).pack(anchor="w", pady=(3, 0))

        actions = tk.Frame(bar, bg=CARD)
        actions.pack(side=tk.RIGHT, padx=(18, 0))
        direct = ttk.Button(
            actions,
            text="直接运行已选",
            command=self._run_serial,
            style="Primary.TButton",
        )
        direct.pack(side=tk.LEFT)
        self._action_buttons.append(direct)
        daily = ttk.Button(
            actions,
            text="一键执行今日任务",
            command=self._run_daily_with_environment,
            style="Soft.TButton",
        )
        daily.pack(side=tk.LEFT, padx=(8, 0))
        self._action_buttons.append(daily)

        tools = tk.Frame(shell, bg="#fafbfe")
        tools.pack(fill=tk.X, padx=1, pady=(0, 1))
        preset = tk.Frame(tools, bg="#fafbfe")
        preset.pack(anchor="w", padx=16, pady=(10, 4))
        tk.Label(
            preset, text="快速选择", bg="#fafbfe", fg=MUTED, font=FONT_UI
        ).pack(side=tk.LEFT, padx=(0, 8))
        for text, command in (
            ("选择今日流程", lambda: self._apply_preset(True)),
            ("选择1分钟试跑", lambda: self._apply_preset(False)),
            ("每周阅读600分钟", self._apply_weekly_reading_preset),
            ("动态规划", self._plan_dynamic_tasks),
            ("全不选", self._clear_task_selection),
        ):
            button = ttk.Button(
                preset, text=text, command=command, style="Toolbar.TButton"
            )
            button.pack(side=tk.LEFT, padx=(0, 6))
            self._action_buttons.append(button)

        utilities = tk.Frame(tools, bg="#fafbfe")
        utilities.pack(anchor="w", padx=16, pady=(0, 10))
        for text, command in (
            ("仅启动环境", self._launch_environment),
            ("启动QQ阅读", lambda: self._run_task("LaunchQQReader")),
            ("识别检查", lambda: self._run_task("SmokeTest")),
            ("运行记录", self._open_record_dir),
            ("设置", self._toggle_settings_panel),
        ):
            button = ttk.Button(
                utilities, text=text, command=command, style="Toolbar.TButton"
            )
            button.pack(side=tk.LEFT, padx=(6, 0))
            self._action_buttons.append(button)

        self._config_var = tk.StringVar()
        self._interval_var = tk.StringVar(value="3")
        self._settings_panel = tk.Frame(shell, bg="#f3f5fb")
        tk.Label(
            self._settings_panel,
            text="本机配置",
            bg="#f3f5fb",
            fg=TEXT,
            font=("Microsoft YaHei UI", 9, "bold"),
        ).pack(side=tk.LEFT, padx=(16, 8), pady=10)
        ttk.Entry(
            self._settings_panel, textvariable=self._config_var, width=52
        ).pack(side=tk.LEFT, pady=10)
        ttk.Button(
            self._settings_panel,
            text="选择…",
            command=self._choose_config,
            style="Toolbar.TButton",
        ).pack(side=tk.LEFT, padx=(6, 0), pady=6)
        ttk.Button(
            self._settings_panel,
            text="重新加载",
            command=self._load_config_from_entry,
            style="Toolbar.TButton",
        ).pack(side=tk.LEFT, padx=(4, 16), pady=6)
        tk.Label(
            self._settings_panel,
            text="任务间隔",
            bg="#f3f5fb",
            fg=MUTED,
            font=FONT_UI,
        ).pack(side=tk.LEFT)
        ttk.Spinbox(
            self._settings_panel,
            from_=0,
            to=120,
            increment=1,
            width=5,
            textvariable=self._interval_var,
        ).pack(side=tk.LEFT, padx=(6, 3))
        tk.Label(
            self._settings_panel, text="秒", bg="#f3f5fb", fg=MUTED
        ).pack(side=tk.LEFT)
        ttk.Button(
            self._settings_panel,
            text="保存任务设置",
            command=self._save_settings,
            style="Toolbar.TButton",
        ).pack(side=tk.RIGHT, padx=16, pady=6)

    def _build_main_panes(self) -> None:
        paned = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 8))

        left = tk.Frame(paned, bg=BG)
        paned.add(left, weight=3)
        left_header = tk.Frame(left, bg=BG)
        left_header.pack(fill=tk.X, padx=4, pady=(0, 6))
        tk.Label(
            left_header,
            text="任务编排",
            bg=BG,
            fg=TEXT,
            font=("Microsoft YaHei UI", 11, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            left_header,
            text="从上到下串行执行；可直接修改次数与时长",
            bg=BG,
            fg=MUTED,
            font=FONT_UI,
        ).pack(side=tk.LEFT, padx=(10, 0))

        canvas = tk.Canvas(left, bg=BG, highlightthickness=0, bd=0)
        scroll = ttk.Scrollbar(left, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._cards_container = tk.Frame(canvas, bg=BG)
        window_id = canvas.create_window(
            (0, 0), window=self._cards_container, anchor="nw"
        )

        def _resize_cards(event: tk.Event) -> None:
            canvas.itemconfigure(window_id, width=event.width)
            canvas.configure(scrollregion=canvas.bbox("all"))

        canvas.bind("<Configure>", _resize_cards)
        self._cards_container.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        self._build_task_cards()

        right = tk.Frame(
            paned, bg=CARD, highlightbackground=BORDER, highlightthickness=1
        )
        paned.add(right, weight=3)
        log_header = tk.Frame(right, bg=CARD)
        log_header.pack(fill=tk.X, padx=12, pady=(8, 4))
        tk.Label(
            log_header,
            text="运行动态",
            bg=CARD,
            fg=TEXT,
            font=("Microsoft YaHei UI", 11, "bold"),
        ).pack(side=tk.LEFT)
        ttk.Button(
            log_header,
            text="清空日志",
            command=self._clear_log,
            style="Toolbar.TButton",
        ).pack(side=tk.RIGHT)
        log_holder = tk.Frame(right, bg=LOG_BG)
        log_holder.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self._log_text = tk.Text(
            log_holder,
            wrap=tk.WORD,
            height=18,
            state=tk.DISABLED,
            bg=LOG_BG,
            fg=LOG_FG,
            insertbackground="#ffffff",
            selectbackground="#334155",
            relief=tk.FLAT,
            font=FONT_MONO,
            padx=8,
            pady=6,
        )
        log_scroll = ttk.Scrollbar(
            log_holder, orient=tk.VERTICAL, command=self._log_text.yview
        )
        self._log_text.configure(yscrollcommand=log_scroll.set)
        self._log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._log_text.tag_configure("info", foreground=LOG_FG)
        self._log_text.tag_configure("observe", foreground="#7dd3fc")
        self._log_text.tag_configure("success", foreground="#4ade80")
        self._log_text.tag_configure("error", foreground="#f87171")
        self._log_text.tag_configure("warn", foreground="#fbbf24")

    def _build_action_bar(self) -> None:
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill=tk.X, padx=20, pady=(2, 14))
        self._stop_button = ttk.Button(
            bar,
            text="停止当前任务",
            command=self._stop_process,
            state=tk.DISABLED,
            style="Danger.TButton",
        )
        self._stop_button.pack(side=tk.RIGHT)

        self._progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(
            bar,
            variable=self._progress_var,
            maximum=100,
            mode="determinate",
            length=220,
        ).pack(side=tk.LEFT, padx=(0, 12))
        self._current_var = tk.StringVar(value="")
        tk.Label(
            bar,
            textvariable=self._current_var,
            bg=BG,
            fg=MUTED,
            font=FONT_UI,
        ).pack(side=tk.LEFT)

    # ------------------------------------------------------------- 任务树

    def _build_task_cards(self) -> None:
        if self._cards_container is None:
            return
        for child in self._cards_container.winfo_children():
            child.destroy()
        self._card_enabled_vars.clear()
        self._card_field_vars.clear()
        visible = [
            spec
            for spec in self._ordered_catalog
            if spec.key not in {"LaunchQQReader", "SmokeTest"}
        ]
        self._build_group_header("每日与可选任务", len(visible))
        for index, spec in enumerate(visible, start=1):
            self._build_task_card(spec, index=index)
        if self._selected_spec not in visible and visible:
            self._selected_spec = visible[0]
        self._refresh_selection_summary()
        container = self._cards_container
        container.update_idletasks()
        canvas = container.master
        if isinstance(canvas, tk.Canvas):
            canvas.configure(scrollregion=canvas.bbox("all"))

    def _build_group_header(self, group: str, count: int) -> None:
        frame = tk.Frame(self._cards_container, bg=BG)
        frame.pack(fill=tk.X, padx=4, pady=(10, 4))
        tk.Label(
            frame,
            text=group,
            bg=BG,
            fg=TEXT,
            font=("Microsoft YaHei UI", 10, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            frame, text=f"{count} 项", bg=BG, fg=MUTED, font=FONT_UI
        ).pack(side=tk.LEFT, padx=(8, 0))
        tk.Frame(frame, bg=BORDER, height=1).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0)
        )

    def _build_task_card(self, spec: TaskSpec, *, index: int) -> None:
        settings = self._settings[spec.key]
        card = tk.Frame(
            self._cards_container,
            bg=CARD,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        card.pack(fill=tk.X, padx=4, pady=4)

        top = tk.Frame(card, bg=CARD)
        top.pack(fill=tk.X, padx=14, pady=(12, 3))
        tk.Label(
            top,
            text=f"{index:02d}",
            bg=ACCENT_SOFT,
            fg=ACCENT_ACTIVE,
            width=3,
            padx=3,
            pady=3,
            font=("Consolas", 9, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 8))
        enabled_var = tk.BooleanVar(value=settings.enabled)
        self._card_enabled_vars[spec.key] = enabled_var
        tk.Checkbutton(
            top,
            text=spec.name,
            variable=enabled_var,
            bg=CARD,
            fg=TEXT,
            activebackground=CARD,
            selectcolor=CARD,
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
            command=lambda s=spec: self._on_card_enabled_changed(s),
        ).pack(side=tk.LEFT)
        tk.Label(
            top,
            text="默认流程" if spec.default_enabled else "可选",
            bg="#ecfdf3" if spec.default_enabled else "#f2f4f7",
            fg=SUCCESS if spec.default_enabled else MUTED,
            font=("Microsoft YaHei UI", 8, "bold"),
            padx=7,
            pady=2,
        ).pack(side=tk.LEFT, padx=(8, 0))
        order = tk.Frame(top, bg=CARD)
        order.pack(side=tk.RIGHT)
        ttk.Button(
            order,
            text="运行此项",
            command=lambda key=spec.key: self._run_task(key),
            style="Soft.TButton",
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            order,
            text="▲",
            width=2,
            command=lambda s=spec: self._move_task(s, -1),
            style="Toolbar.TButton",
        ).pack(side=tk.LEFT)
        ttk.Button(
            order,
            text="▼",
            width=2,
            command=lambda s=spec: self._move_task(s, 1),
            style="Toolbar.TButton",
        ).pack(side=tk.LEFT, padx=(4, 0))

        tk.Label(
            card,
            text=spec.description,
            bg=CARD,
            fg=MUTED,
            font=FONT_UI,
            wraplength=540,
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, padx=12, pady=(0, 6))

        fields = tk.Frame(card, bg=CARD)
        fields.pack(fill=tk.X, padx=14, pady=(1, 12))
        self._card_field_vars[spec.key] = {}
        for index, item in enumerate(spec.fields):
            column = index * 3
            tk.Label(
                fields, text=item.label, bg=CARD, fg=TEXT, font=FONT_UI
            ).grid(row=0, column=column, sticky=tk.W, padx=(0, 4))
            current = settings.value(spec, item.key)
            if item.kind == "bool":
                var: tk.Variable = tk.BooleanVar(value=bool(current))
                widget = tk.Checkbutton(
                    fields,
                    variable=var,
                    bg=CARD,
                    activebackground=CARD,
                    selectcolor=CARD,
                )
            else:
                var = tk.StringVar(
                    value=f"{current:g}" if isinstance(current, float) else str(current)
                )
                widget = ttk.Spinbox(
                    fields,
                    from_=item.minimum if item.minimum is not None else 0,
                    to=item.maximum if item.maximum is not None else 999999,
                    increment=item.step,
                    width=8,
                    textvariable=var,
                )
                var.trace_add(
                    "write",
                    lambda *_args, s=spec, key=item.key: self._on_card_field_changed(
                        s, key
                    ),
                )
            widget.grid(row=0, column=column + 1, sticky=tk.W, padx=(0, 12))
            if item.unit:
                tk.Label(
                    fields, text=item.unit, bg=CARD, fg=MUTED, font=FONT_UI
                ).grid(row=0, column=column + 2, sticky=tk.W, padx=(0, 12))
            self._card_field_vars[spec.key][item.key] = var

        for widget in (card, top, fields):
            widget.bind("<Button-1>", lambda _event, s=spec: self._select_card(s))

    def _refresh_selection_summary(self) -> None:
        if not hasattr(self, "_selection_summary_var"):
            return
        enabled_specs = [
            spec
            for spec in self._ordered_catalog
            if self._settings[spec.key].enabled
            and spec.key not in {"LaunchQQReader", "SmokeTest"}
        ]
        try:
            plan = build_serial_plan(
                self._settings,
                self._catalog,
                order=[spec.key for spec in self._ordered_catalog],
            )
        except ValueError:
            self._selection_summary_var.set("任务参数需要检查")
            self._selection_detail_var.set("请修正红框或无效数字后再运行")
            return
        minutes = 0.0
        for item in plan:
            value = item.settings.value(item.spec, "minutes", None)
            if value is None:
                value = item.settings.value(item.spec, "duration_minutes", 0)
            minutes += float(value or 0)
        self._selection_summary_var.set(
            f"已选择 {len(enabled_specs)} 项 · 实际执行 {len(plan)} 步"
            + (f" · 计时约 {minutes:g} 分钟" if minutes else "")
        )
        names = " → ".join(spec.name for spec in enabled_specs)
        self._selection_detail_var.set(names or "尚未选择任务")

    def _select_card(self, spec: TaskSpec) -> None:
        self._selected_spec = spec

    def _on_card_enabled_changed(self, spec: TaskSpec) -> None:
        var = self._card_enabled_vars.get(spec.key)
        if var is None:
            return
        self._settings[spec.key].enabled = bool(var.get())
        self._log(
            f"[任务] {spec.display_name} {'启用' if var.get() else '停用'}"
        )
        self._save_settings(silent=True)
        self._refresh_selection_summary()

    def _on_card_field_changed(self, spec: TaskSpec, key: str) -> None:
        var = self._card_field_vars.get(spec.key, {}).get(key)
        if var is None:
            return
        try:
            value = spec.field(key).normalize(var.get())
        except (tk.TclError, ValueError):
            return
        self._settings[spec.key].values[key] = value
        self._save_settings(silent=True)
        self._refresh_selection_summary()

    # ------------------------------------------------------------- 配置

    def _choose_config(self) -> None:
        path = filedialog.askopenfilename(
            title="选择 QQReader 配置文件",
            filetypes=[
                ("QQReader 配置", "*.json *.yaml *.yml"),
                ("所有文件", "*.*"),
            ],
        )
        if path:
            self._config_var.set(path)
            self._load_config(Path(path))

    def _toggle_settings_panel(self) -> None:
        if self._settings_panel.winfo_manager():
            self._settings_panel.pack_forget()
            self._log("[界面] 已收起本机设置")
        else:
            self._settings_panel.pack(fill=tk.X, padx=1, pady=(0, 1))
            self._log("[界面] 已展开本机设置")

    def _load_config_from_entry(self) -> None:
        raw = self._config_var.get().strip()
        if not raw:
            messagebox.showwarning("配置", "请先选择配置文件")
            return
        self._load_config(Path(raw))

    def _load_config(self, path: Path) -> None:
        try:
            config = load_config(path)
        except (ConfigError, OSError) as exc:
            self._config = None
            self._log(f"[配置错误] {exc}")
            messagebox.showerror("配置错误", str(exc))
            return
        self._config = config
        self._config_var.set(str(path))
        self._log(f"[配置] 已加载 {path}")
        for line in config.describe().splitlines():
            self._log("  " + line)

    def _require_config(self) -> Optional[AppConfig]:
        if self._config is None:
            messagebox.showwarning("配置", "请先加载本机配置文件")
            return None
        return self._config

    # ------------------------------------------------------------- 设置持久化

    def _settings_path(self) -> Path:
        return self.repo_root / "runtime" / "gui_tasks.json"

    def _load_task_settings_file(self) -> None:
        path = self._settings_path()
        self._settings = load_task_settings(path, self._catalog)
        self._ordered_catalog = load_task_order(path, self._catalog)
        if self._cards_container is not None:
            self._build_task_cards()

    def _save_settings(self, *, silent: bool = False) -> None:
        try:
            save_task_settings(
                self._settings_path(),
                self._settings,
                self._catalog,
                order=[spec.key for spec in self._ordered_catalog],
            )
        except OSError as exc:
            self._log(f"[设置] 保存失败: {exc}")
            return
        if not silent:
            self._log(f"[设置] 已保存到 {self._settings_path()}")

    def _move_task(self, spec: TaskSpec, direction: int) -> None:
        if self._busy:
            return
        keys = [item.key for item in self._ordered_catalog]
        visible_keys = [
            key for key in keys if key not in {"LaunchQQReader", "SmokeTest"}
        ]
        try:
            index = visible_keys.index(spec.key)
        except ValueError:
            return
        target = index + direction
        if target < 0 or target >= len(visible_keys):
            return
        first = keys.index(visible_keys[index])
        second = keys.index(visible_keys[target])
        keys[first], keys[second] = keys[second], keys[first]
        by_key = {item.key: item for item in self._catalog}
        self._ordered_catalog = [by_key[key] for key in keys]
        self._selected_spec = spec
        self._build_task_cards()
        self._log(
            f"[任务] {spec.display_name} 已{'上移' if direction < 0 else '下移'}"
        )
        self._save_settings(silent=True)

    def _move_selected(self, direction: int) -> None:
        if self._selected_spec is None:
            return
        self._move_task(self._selected_spec, direction)

    def _apply_preset(self, formal: bool) -> None:
        if self._busy:
            return
        apply_daily_preset(
            self._settings,
            formal=formal,
            catalog=self._catalog,
        )
        self._build_task_cards()
        self._save_settings(silent=True)
        self._log(
            "[预设] 已选择今日流程：阅读→听书→游戏→奖励页广告→等级广告"
            if formal
            else "[预设] 已选择1分钟试跑：阅读→听书→游戏，各运行1次"
        )

    def _clear_task_selection(self) -> None:
        if self._busy:
            return
        for settings in self._settings.values():
            settings.enabled = False
        self._build_task_cards()
        self._save_settings(silent=True)
        self._log("[任务] 已取消全部勾选")

    def _apply_weekly_reading_preset(self) -> None:
        if self._busy:
            return
        apply_weekly_reading_preset(self._settings, catalog=self._catalog)
        self._build_task_cards()
        self._save_settings(silent=True)
        self._log(
            "[预设] 已选择每周阅读：仅自动阅读，10次×35分钟；其他任务已关闭"
        )

    def _plan_dynamic_tasks(self) -> None:
        config = self._require_config()
        if config is None or self._busy:
            return
        python, python_args = self._python_launcher(config)
        command = [python, *python_args, str(self.repo_root / "scripts" / "dynamic_plan.py"),
                   "--config", self._config_var.get()]
        self._start_process(command, status="读取奖励页并规划任务", on_finish=self._on_dynamic_plan_finished)

    def _on_dynamic_plan_finished(self, code: int) -> None:
        if code == 0:
            self._load_task_settings_file()
            self._set_status("规划完成，请直接运行已选")
        else:
            self._set_status("规划未完成，请查看日志")

    # ------------------------------------------------------------- 模拟器

    def _launch_emulator(self) -> None:
        config = self._require_config()
        if config is None or self._busy:
            return
        if not config.machine.emulator_path:
            messagebox.showwarning("模拟器", "配置里没有 machine.emulator_path")
            return
        try:
            command = build_emulator_launch_command(
                Path(config.machine.emulator_path)
            )
        except ValueError as exc:
            self._log(f"[模拟器错误] {exc}")
            return
        self._log("[模拟器] " + command_preview(command))
        self._start_process(
            command,
            status="启动模拟器",
            on_finish=self._on_emulator_finished,
        )

    def _run_daily_with_environment(self) -> None:
        """日常主入口：恢复正式预设，准备环境后直接开始整轮任务。"""
        if self._busy:
            return
        self._apply_preset(True)
        self._log("[一键执行] 已恢复正式参数，开始准备模拟器和 QQ 阅读")
        self._launch_environment(run_daily=True)

    def _launch_environment(self, run_daily: bool = False) -> None:
        """一次完成模拟器启动、ADB 就绪和 QQ 阅读开屏清理。"""
        config = self._require_config()
        if config is None or self._busy:
            return
        if not config.machine.emulator_path:
            messagebox.showwarning("模拟器", "配置里没有 machine.emulator_path")
            return
        try:
            command = build_emulator_launch_command(Path(config.machine.emulator_path))
        except ValueError as exc:
            self._log(f"[模拟器错误] {exc}")
            return
        self._log("[一键启动] 启动模拟器，设备就绪后自动启动 QQ 阅读")
        self._start_process(
            command,
            status="一键启动环境",
            on_finish=lambda code: self._on_emulator_finished(
                code, launch_reader=True, run_daily=run_daily
            ),
        )

    def _on_emulator_finished(
        self,
        code: int,
        launch_reader: bool = False,
        run_daily: bool = False,
    ) -> None:
        self._log(f"[模拟器] 启动命令 exit={code}")
        config = self._config
        if config is None:
            return
        command = build_adb_connect_command(
            config.machine.adb_path, config.machine.adb_address
        )
        self._log("[ADB] " + command_preview(command))

        def worker() -> None:
            from ..maa.adb import ensure_maa_ready

            ready, detail = ensure_maa_ready(
                config.machine.adb_path,
                config.machine.adb_address,
                package_name=config.machine.package_name,
                timeout=60.0,
            )
            self._log(f"[ADB] {detail}")
            if not ready:
                self._log("[ADB] 设备未就绪，启动任务时仍会再次重试。")
                if run_daily:
                    self.root.after(0, lambda: self._set_status("设备未就绪"))
            elif launch_reader:
                self._log("[一键启动] 设备已就绪，启动 QQ 阅读并清理弹窗")
                callback = (
                    self._start_reader_before_daily
                    if run_daily
                    else lambda: self._run_task("LaunchQQReader")
                )
                self.root.after(0, callback)

        threading.Thread(target=worker, daemon=True).start()

    def _start_reader_before_daily(self) -> None:
        config = self._require_config()
        if config is None or self._busy:
            return
        spec = next(item for item in self._catalog if item.key == "LaunchQQReader")
        python_executable, python_args = self._python_launcher(config)
        try:
            command = build_run_task_command(
                python_executable,
                self.repo_root,
                Path(self._config_var.get()),
                spec.key,
                python_args=python_args,
                settings=self._settings[spec.key].normalized(spec).values,
            )
        except ValueError as exc:
            self._log(f"[一键执行] 启动参数错误: {exc}")
            self._set_status("启动参数错误")
            return
        self._start_process(
            command,
            status="正在启动 QQ 阅读",
            on_finish=self._on_reader_before_daily_finished,
        )

    def _on_reader_before_daily_finished(self, code: int) -> None:
        if code != 0:
            self._log(f"[一键执行] QQ 阅读启动清理失败 exit={code}，未开始每日任务")
            self._set_status("QQ 阅读启动失败")
            return
        self._log("[一键执行] 环境准备完成，开始今日任务")
        self.root.after(300, self._run_serial)

    # ------------------------------------------------------------- 串行执行

    def _python_launcher(self, config: AppConfig) -> tuple[str, tuple[str, ...]]:
        configured = config.machine.python_executable
        if configured:
            return str(configured), ()
        if getattr(sys, "frozen", False):
            python = shutil.which("python")
            if python:
                return python, ()
            py_launcher = shutil.which("py")
            if py_launcher:
                return py_launcher, ("-3.10",)
            return "python", ()
        return sys.executable, ()

    def _run_serial(self) -> None:
        if not self._prepare_serial():
            return
        self._serial_plan = build_serial_plan(
            self._settings,
            self._catalog,
            order=[spec.key for spec in self._ordered_catalog],
        )
        self._start_serial_plan()

    def _run_task(self, key: str) -> None:
        """工具栏快捷按钮：运行单个指定任务。"""
        spec = next((item for item in self._catalog if item.key == key), None)
        if spec is None:
            return
        if not self._prepare_serial():
            return
        settings = self._settings[spec.key].normalized(spec)
        self._serial_plan = [TaskRunPlan(spec=spec, settings=settings)]
        self._start_serial_plan()

    def _run_selected(self) -> None:
        spec = self._selected_spec
        if spec is None:
            messagebox.showwarning("任务", "请先在左侧选择一个任务")
            return
        if not self._prepare_serial():
            return
        settings = self._settings[spec.key].normalized(spec)
        self._serial_plan = [TaskRunPlan(spec=spec, settings=settings)]
        self._start_serial_plan()

    def _prepare_serial(self) -> bool:
        config = self._require_config()
        if config is None or self._busy:
            return False
        return True

    def _start_serial_plan(self) -> None:
        if not self._serial_plan:
            messagebox.showinfo("串行执行", "没有已启用的任务")
            return
        script = self.repo_root / "scripts" / "run_task.py"
        if not script.is_file():
            messagebox.showerror("脚本缺失", f"找不到 {script}")
            return
        config = self._require_config()
        if config is None:
            return
        self._serial_index = 0
        self._progress_var.set(0)
        self._stopping = False
        self._serial_run = DailyFlowRun.start(
            snapshots_from_plans(self._serial_plan),
            config_path=self._config_var.get().strip(),
        )
        self._serial_recorder = DailyFlowRecorder(Path(config.machine.record_dir))
        self._save_serial_run()
        self._log(
            f"[串行] 共 {len(self._serial_plan)} 个任务，按顺序执行；"
            f"run={self._serial_run.run_id} 业务日={self._serial_run.business_day}"
        )
        if self._serial_record_path is not None:
            self._log(f"[串行记录] {self._serial_record_path}")
        self._start_next_task()

    def _start_next_task(self) -> None:
        if self._stopping:
            return
        if self._serial_index >= len(self._serial_plan):
            self._finish_serial()
            return
        config = self._require_config()
        if config is None:
            return
        plan = self._serial_plan[self._serial_index]
        python_executable, python_args = self._python_launcher(config)
        try:
            command = build_run_task_command(
                python_executable,
                self.repo_root,
                Path(self._config_var.get()),
                plan.spec.key,
                python_args=python_args,
                settings=plan.settings.values,
            )
        except ValueError as exc:
            self._log(f"[串行] 参数错误: {exc}")
            if self._serial_run is not None:
                self._serial_run.complete_current(2, reason=f"参数错误: {exc}")
                self._save_serial_run()
            self._serial_index += 1
            self._start_next_record_step()
            self.root.after(500, self._start_next_task)
            return
        index = self._serial_index + 1
        total = len(self._serial_plan)
        self._progress_var.set((index - 1) / total * 100)
        repeat = (
            f"（重复 {plan.repeat_index}/{plan.repeat_total}）"
            if plan.repeat_total > 1
            else ""
        )
        self._current_var.set(
            f"当前：{plan.spec.display_name} ({index}/{total})"
        )
        self._log(
            f"[{index}/{total}] {plan.spec.display_name} ({plan.spec.key})"
            f"{repeat} 开始\n"
            f"      {command_preview(command)}"
        )
        self._start_process(
            command,
            status=f"运行中：{plan.spec.display_name}",
            on_finish=self._on_task_finished,
        )

    def _on_task_finished(self, code: int) -> None:
        if self._stopping:
            if (
                self._serial_run is not None
                and self._serial_run.state is FlowRunState.RUNNING
            ):
                self._serial_run.stop_by_user()
                self._save_serial_run()
            self._log("[串行] 已停止；当前任务已取消，后续任务已跳过")
            self._finish_serial()
            return
        plan = self._serial_plan[self._serial_index]
        if self._serial_run is not None:
            self._serial_run.complete_current(code)
            self._save_serial_run()
        if code == 0:
            self._log(
                f"[{self._serial_index + 1}/{len(self._serial_plan)}] "
                f"{plan.spec.display_name} 成功"
            )
        else:
            self._log(
                f"[{self._serial_index + 1}/{len(self._serial_plan)}] "
                f"{plan.spec.display_name} 失败 exit={code}"
            )
        self._progress_var.set(
            (self._serial_index + 1) / len(self._serial_plan) * 100
        )
        self._serial_index += 1
        self._start_next_record_step()
        self.root.after(self._interval_seconds() * 1000, self._start_next_task)

    def _start_next_record_step(self) -> None:
        run = self._serial_run
        if run is None or run.state is not FlowRunState.RUNNING:
            return
        run.start_next()
        self._save_serial_run()

    def _save_serial_run(self) -> None:
        if self._serial_run is None or self._serial_recorder is None:
            return
        try:
            self._serial_record_path = self._serial_recorder.save(self._serial_run)
        except OSError as exc:
            self._log(f"[串行记录] 保存失败: {exc}")

    def _interval_seconds(self) -> int:
        try:
            return max(0, int(float(self._interval_var.get())))
        except ValueError:
            return 0

    def _finish_serial(self) -> None:
        run = self._serial_run
        self._current_var.set("本轮运行结束")
        if run is None:
            self._set_status("串行执行结束")
            return
        counts = run.counts()
        success = counts[FlowStepState.SUCCEEDED.value]
        failed = counts[FlowStepState.FAILED.value]
        skipped = counts[FlowStepState.SKIPPED.value]
        if run.state is FlowRunState.CANCELLED:
            summary = f"已停止：成功 {success}，失败 {failed}，跳过 {skipped}"
        elif run.state is FlowRunState.COMPLETED_WITH_ERRORS:
            summary = f"完成但有错误：成功 {success}，失败 {failed}"
        else:
            summary = f"全部成功：{success} 项"
        self._progress_var.set(100)
        self._set_status(summary)
        self._log(f"[串行] {summary}")
        if self._serial_record_path is not None:
            self._log(f"[串行记录] {self._serial_record_path}")

    # ------------------------------------------------------------- 进程管理

    def _start_process(
        self,
        command: Sequence[str],
        *,
        status: str,
        on_finish: Optional[Callable[[int], None]] = None,
    ) -> None:
        if self._busy:
            self._log("[提示] 已有任务在运行，请先停止")
            return
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            process = subprocess.Popen(
                list(command),
                cwd=str(self.repo_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
            )
        except OSError as exc:
            self._log(f"[启动失败] {exc}")
            if on_finish is not None:
                on_finish(1)
            return
        self._process = process
        self._busy = True
        self._stopping = False
        self._finish_callback = on_finish
        self._set_running_ui(True)
        self._set_status(status)
        threading.Thread(
            target=self._read_process_output, args=(process,), daemon=True
        ).start()

    def _read_process_output(self, process: subprocess.Popen) -> None:
        if process.stdout is not None:
            for line in process.stdout:
                self._log_queue.put(line.rstrip("\n"))
        code = process.wait()
        self._log_queue.put(f"[进程结束] exit={code}")
        self._log_queue.put(f"__PROCESS_FINISHED__:{code}")

    def _drain_log_queue(self) -> None:
        while True:
            try:
                line = self._log_queue.get_nowait()
            except queue.Empty:
                break
            if line.startswith("__PROCESS_FINISHED__:"):
                self._on_process_finished(int(line.split(":", 1)[1]))
            else:
                self._log(line)
        self.root.after(100, self._drain_log_queue)

    def _on_process_finished(self, code: int) -> None:
        self._busy = False
        self._process = None
        self._set_running_ui(False)
        callback = self._finish_callback
        self._finish_callback = None
        if callback is not None:
            callback(code)

    def _set_running_ui(self, running: bool) -> None:
        state = tk.DISABLED if running else tk.NORMAL
        for button in getattr(self, "_action_buttons", []):
            button.configure(state=state)
        self._stop_button.configure(state=tk.NORMAL if running else tk.DISABLED)

    def _stop_process(self) -> None:
        if self._process is None or self._process.poll() is not None:
            return
        self._stopping = True
        self._log("[停止] 正在结束当前任务…")
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(self._process.pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                )
            else:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
        except OSError as exc:
            self._log(f"[停止失败] {exc}")
        self._set_status("正在停止…")

    # ------------------------------------------------------------- 日志等

    def _open_record_dir(self) -> None:
        config = self._config
        if config is None:
            messagebox.showwarning("记录目录", "请先加载配置")
            return
        path = Path(config.machine.record_dir)
        if not path.exists():
            self._log(f"[记录目录] 不存在: {path}")
            return
        try:
            if os.name == "nt":
                os.startfile(str(path))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except OSError as exc:
            self._log(f"[记录目录] 打开失败: {exc}")

    def _clear_log(self) -> None:
        self._log_text.configure(state=tk.NORMAL)
        self._log_text.delete("1.0", tk.END)
        self._log_text.configure(state=tk.DISABLED)

    def _log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        tag = "info"
        if "[observe" in message:
            tag = "observe"
        elif any(
            token in message
            for token in ("失败", "错误", "[ERR]", "[not-implemented]")
        ):
            tag = "error"
        elif "未接入" in message or "旧流程" in message:
            tag = "warn"
        elif any(token in message for token in ("成功", "完成")):
            tag = "success"
        self._log_text.configure(state=tk.NORMAL)
        self._log_text.insert(tk.END, f"[{timestamp}] {message}\n", tag)
        self._log_text.see(tk.END)
        self._log_text.configure(state=tk.DISABLED)

    def _set_status(self, text: str) -> None:
        self._status_var.set(text)
        color = MUTED
        if any(token in text for token in ("运行中", "启动")):
            color = ACCENT
        elif any(token in text for token in ("失败", "错误")):
            color = DANGER
        elif any(token in text for token in ("完成", "成功")):
            color = SUCCESS
        elif "停止" in text:
            color = WARNING
        self._status_dot.configure(fg=color)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QQReader 每日任务 GUI")
    parser.add_argument("--config", default=None, help="本机配置文件")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    root = tk.Tk()
    QQReaderGui(
        root,
        config_path=Path(args.config) if args.config else None,
    )
    root.mainloop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
