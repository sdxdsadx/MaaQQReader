"""QQReader 每日任务控制台：侧边栏 + 任务队列 + 任务详情 + 本轮进度 + 运行日志。"""

from __future__ import annotations

import argparse
import base64
import dataclasses
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..config import AppConfig, ConfigError, load_config
from ..runner.exit_codes import describe_exit_code
from ..workflow import (
    DailyFlowRecorder,
    DailyFlowRun,
    FlowRunState,
    FlowStepState,
    apply_handoff,
    handoff_report_path,
    load_handoff_report,
    snapshots_from_plans,
)
from . import cover as cover_tools
from . import theme
from .commands import (
    build_adb_connect_command,
    build_adb_devices_command,
    build_emulator_launch_command,
    build_handoff_command,
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
from .device import (
    candidate_addresses,
    child_env,
    describe_devices,
    load_device_address,
    mumu_default_addresses,
    parse_adb_devices,
    save_device_address,
    validate_address,
)
from .widgets import TaskRow, describe_settings, make_card


def _detect_repo_root() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
        for candidate in (base, *base.parents):
            if (candidate / "scripts" / "run_task.py").is_file():
                return candidate
        return base
    return Path(__file__).resolve().parents[2]


_REPO_ROOT = _detect_repo_root()

# 只在工具栏快捷按钮中出现，不进入任务队列
_HIDDEN_TASKS = frozenset({"LaunchQQReader", "SmokeTest"})
# 日志区最多保留的行数，避免长时间运行后界面变卡
_LOG_MAX_LINES = 5000


class QQReaderGui:
    """任务队列 + 参数详情 + 串行执行的 GUI。"""

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
        self._task_rows: Dict[str, TaskRow] = {}
        self._queue_container: Optional[tk.Frame] = None
        self._detail_body: Optional[tk.Frame] = None
        self._detail_run_button: Optional[ttk.Button] = None
        self._serial_plan: List[TaskRunPlan] = []
        self._serial_index = 0
        self._serial_run: Optional[DailyFlowRun] = None
        self._serial_recorder: Optional[DailyFlowRecorder] = None
        self._serial_record_path: Optional[Path] = None
        self._run_started_at: Optional[float] = None
        self._current_text = ""
        # 模拟器地址：GUI 选择优先于配置文件，经 QQREADER_ADB_ADDRESS 传给子进程。
        self._adb_override = load_device_address(self._device_path())
        self._configured_adb_address = ""
        self._scanned_devices: List[tuple] = []

        self._build_ui()
        self._load_task_settings_file()
        if config_path is not None:
            self._load_config(Path(config_path))

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        self.root.title("QQReader 每日任务控制台")
        self.root.geometry("1360x860")
        self.root.minsize(1120, 720)
        self.root.configure(bg=theme.BG)
        theme.configure_styles(self.root)
        self._action_buttons: List[ttk.Button] = []

        self._build_sidebar()
        self._content = tk.Frame(self.root, bg=theme.BG)
        self._content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._build_header()
        self._build_action_bar()
        self._build_settings_panel()
        self._build_main_panes()
        self._bind_shortcuts()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._drain_log_queue)
        self.root.after(1000, self._tick_elapsed)
        self._log(
            "GUI 已启动。日常使用只需点击「一键执行今日任务」；"
            "需要调试时可选择1分钟试跑或单独运行任务。"
        )

    def _build_sidebar(self) -> None:
        side = tk.Frame(self.root, bg=theme.SIDEBAR, width=200)
        side.pack(side=tk.LEFT, fill=tk.Y)
        side.pack_propagate(False)

        brand = tk.Frame(side, bg=theme.SIDEBAR)
        brand.pack(fill=tk.X, padx=16, pady=(18, 14))
        tk.Label(
            brand,
            text="QQReader",
            bg=theme.SIDEBAR,
            fg="#ffffff",
            font=theme.FONT_TITLE,
        ).pack(anchor="w")
        tk.Label(
            brand,
            text="每日任务自动化",
            bg=theme.SIDEBAR,
            fg=theme.SIDEBAR_MUTED,
            font=theme.FONT_UI,
        ).pack(anchor="w")

        self._nav_section(
            side,
            "快速选择",
            (
                ("选择今日流程", lambda: self._apply_preset(True)),
                ("选择1分钟试跑", lambda: self._apply_preset(False)),
                ("每周阅读600分钟", self._apply_weekly_reading_preset),
                ("动态规划", self._plan_dynamic_tasks),
                ("全不选", self._clear_task_selection),
            ),
        )
        self._nav_section(
            side,
            "环境与工具",
            (
                ("仅启动环境", self._launch_environment),
                ("启动QQ阅读", lambda: self._run_task("LaunchQQReader")),
                ("识别检查", lambda: self._run_task("SmokeTest")),
                ("运行记录", self._open_record_dir),
                ("设置", self._toggle_settings_panel),
            ),
        )

        footer = tk.Frame(side, bg=theme.SIDEBAR)
        footer.pack(side=tk.BOTTOM, fill=tk.X, padx=16, pady=14)
        tk.Label(
            footer,
            text="本机配置",
            bg=theme.SIDEBAR,
            fg=theme.SIDEBAR_MUTED,
            font=theme.FONT_SMALL,
        ).pack(anchor="w")
        self._config_state_var = tk.StringVar(value="未加载")
        self._config_state_label = tk.Label(
            footer,
            textvariable=self._config_state_var,
            bg=theme.SIDEBAR,
            fg=theme.WARNING,
            font=theme.FONT_BOLD,
            anchor="w",
            wraplength=168,
            justify=tk.LEFT,
        )
        self._config_state_label.pack(anchor="w", fill=tk.X)

    def _nav_section(self, parent: tk.Misc, title: str, items) -> None:
        tk.Label(
            parent,
            text=title,
            bg=theme.SIDEBAR,
            fg=theme.SIDEBAR_MUTED,
            font=theme.FONT_SMALL,
        ).pack(anchor="w", padx=18, pady=(12, 4))
        for text, command in items:
            button = ttk.Button(parent, text=text, command=command, style="Nav.TButton")
            button.pack(fill=tk.X, padx=8, pady=1)
            self._action_buttons.append(button)

    def _build_header(self) -> None:
        header = tk.Frame(self._content, bg=theme.BG)
        header.pack(fill=tk.X, padx=20, pady=(16, 10))

        overview = tk.Frame(header, bg=theme.BG)
        overview.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(
            overview,
            text="今天的任务",
            bg=theme.BG,
            fg=theme.TEXT,
            font=theme.FONT_HEADING,
        ).pack(anchor="w")
        self._selection_summary_var = tk.StringVar(value="正在读取任务设置…")
        tk.Label(
            overview,
            textvariable=self._selection_summary_var,
            bg=theme.BG,
            fg=theme.ACCENT_ACTIVE,
            font=(theme.FONT_FAMILY, 10, "bold"),
        ).pack(anchor="w", pady=(4, 0))
        self._selection_detail_var = tk.StringVar(value="")
        tk.Label(
            overview,
            textvariable=self._selection_detail_var,
            bg=theme.BG,
            fg=theme.MUTED,
            font=theme.FONT_UI,
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

        pill = tk.Frame(
            header,
            bg=theme.SURFACE,
            highlightbackground=theme.BORDER,
            highlightthickness=1,
        )
        pill.pack(side=tk.RIGHT, anchor="n")
        self._build_device_selector(header)
        self._status_var = tk.StringVar(value="准备就绪")
        self._status_dot = tk.Label(
            pill, text="●", bg=theme.SURFACE, fg=theme.MUTED, font=("Segoe UI", 11)
        )
        self._status_dot.pack(side=tk.LEFT, padx=(12, 0), pady=6)
        tk.Label(
            pill,
            textvariable=self._status_var,
            bg=theme.SURFACE,
            fg=theme.TEXT,
            font=theme.FONT_BOLD,
        ).pack(side=tk.LEFT, padx=(6, 14), pady=6)
        self._header = header

    def _build_device_selector(self, header: tk.Frame) -> None:
        """标题栏右侧：选择模拟器 ADB 地址（下拉候选 + 手动输入）。"""
        box = tk.Frame(header, bg=theme.BG)
        box.pack(side=tk.RIGHT, anchor="n", padx=(0, 12))
        row = tk.Frame(box, bg=theme.BG)
        row.pack(anchor="e")
        tk.Label(
            row, text="模拟器", bg=theme.BG, fg=theme.TEXT, font=theme.FONT_BOLD
        ).pack(side=tk.LEFT, padx=(0, 6))
        self._device_var = tk.StringVar(value=self._adb_override)
        self._device_combo = ttk.Combobox(
            row, textvariable=self._device_var, width=22
        )
        self._device_combo.pack(side=tk.LEFT)
        self._device_combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_device())
        self._device_combo.bind("<Return>", lambda _e: self._apply_device())
        for text, command in (
            ("应用", self._apply_device),
            ("扫描", self._scan_devices),
            ("跟随配置", self._reset_device),
        ):
            button = ttk.Button(row, text=text, command=command, style="Toolbar.TButton")
            button.pack(side=tk.LEFT, padx=(4, 0))
            self._action_buttons.append(button)
        self._device_hint_var = tk.StringVar(value="")
        tk.Label(
            box,
            textvariable=self._device_hint_var,
            bg=theme.BG,
            fg=theme.MUTED,
            font=theme.FONT_SMALL,
            anchor="e",
        ).pack(anchor="e", pady=(3, 0))
        self._refresh_device_selector()

    def _build_settings_panel(self) -> None:
        self._config_var = tk.StringVar()
        self._interval_var = tk.StringVar(value="3")
        panel = tk.Frame(
            self._content,
            bg=theme.SURFACE,
            highlightbackground=theme.BORDER,
            highlightthickness=1,
        )
        self._settings_panel = panel
        row = tk.Frame(panel, bg=theme.SURFACE)
        row.pack(fill=tk.X, padx=14, pady=10)
        tk.Label(
            row, text="配置文件", bg=theme.SURFACE, fg=theme.TEXT, font=theme.FONT_BOLD
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Entry(row, textvariable=self._config_var, width=56).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        ttk.Button(
            row, text="选择…", command=self._choose_config, style="Toolbar.TButton"
        ).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(
            row,
            text="重新加载",
            command=self._load_config_from_entry,
            style="Toolbar.TButton",
        ).pack(side=tk.LEFT, padx=(4, 16))
        tk.Label(
            row, text="任务间隔", bg=theme.SURFACE, fg=theme.MUTED, font=theme.FONT_UI
        ).pack(side=tk.LEFT)
        ttk.Spinbox(
            row,
            from_=0,
            to=120,
            increment=1,
            width=5,
            textvariable=self._interval_var,
        ).pack(side=tk.LEFT, padx=(6, 3))
        tk.Label(row, text="秒", bg=theme.SURFACE, fg=theme.MUTED).pack(side=tk.LEFT)
        ttk.Button(
            row,
            text="保存任务设置",
            command=self._save_settings,
            style="Toolbar.TButton",
        ).pack(side=tk.LEFT, padx=(16, 0))
        tk.Label(
            panel,
            text="任务勾选/次数/顺序自动保存到 runtime/gui_tasks.json　·　快捷键：F5 运行已选，Ctrl+S 保存，Ctrl+L 清空日志",
            bg=theme.SURFACE,
            fg=theme.SUBTLE,
            font=theme.FONT_SMALL,
            anchor="w",
        ).pack(fill=tk.X, padx=14, pady=(0, 8))

    def _build_main_panes(self) -> None:
        paned = ttk.Panedwindow(self._content, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))
        self._main_area = paned

        # 左：任务队列
        queue_card, queue_header, queue_body = make_card(paned, "任务队列")
        paned.add(queue_card, weight=2)
        self._queue_count_var = tk.StringVar()
        tk.Label(
            queue_header,
            textvariable=self._queue_count_var,
            bg=theme.SURFACE,
            fg=theme.MUTED,
            font=theme.FONT_UI,
        ).pack(side=tk.RIGHT)
        self._queue_container = tk.Frame(queue_body, bg=theme.SURFACE)
        self._queue_container.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 8))

        # 中：任务详情（自然高度）+ 执行计划/本轮进度（占满剩余）
        middle = tk.Frame(paned, bg=theme.BG)
        paned.add(middle, weight=2)
        detail_card, _detail_header, detail_body = make_card(middle, "任务详情")
        detail_card.pack(fill=tk.X)
        self._detail_body = detail_body

        steps_card, steps_header, steps_body = make_card(middle, "执行计划")
        steps_card.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self._steps_title = steps_header.winfo_children()[0]
        self._steps_hint_var = tk.StringVar()
        tk.Label(
            steps_header,
            textvariable=self._steps_hint_var,
            bg=theme.SURFACE,
            fg=theme.MUTED,
            font=theme.FONT_UI,
        ).pack(side=tk.RIGHT)
        self._build_steps_view(steps_body)

        # 右：运行日志
        log_card, log_header, log_body = make_card(paned, "运行日志")
        paned.add(log_card, weight=3)
        ttk.Button(
            log_header,
            text="清空日志",
            command=self._clear_log,
            style="Toolbar.TButton",
        ).pack(side=tk.RIGHT)
        self._autoscroll_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            log_header,
            text="自动滚动",
            variable=self._autoscroll_var,
            bg=theme.SURFACE,
            activebackground=theme.SURFACE,
            fg=theme.MUTED,
            font=theme.FONT_UI,
        ).pack(side=tk.RIGHT, padx=(0, 6))
        self._build_log_view(log_body)

        # 首次显示时按比例设定三栏宽度：队列 / 详情 / 日志
        def _init_sashes(event: tk.Event) -> None:
            paned.unbind("<Configure>")
            if event.width > 600:
                paned.sashpos(0, int(event.width * 0.30))
                paned.sashpos(1, int(event.width * 0.62))

        paned.bind("<Configure>", _init_sashes)

    def _build_steps_view(self, parent: tk.Frame) -> None:
        holder = tk.Frame(parent, bg=theme.SURFACE)
        holder.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        tree = ttk.Treeview(
            holder,
            columns=("index", "task", "state", "time"),
            show="headings",
            style="Steps.Treeview",
            selectmode="none",
            height=6,
        )
        for column, text, width, anchor in (
            ("index", "#", 32, tk.CENTER),
            ("task", "任务", 140, tk.W),
            ("state", "状态", 80, tk.W),
            ("time", "耗时", 60, tk.CENTER),
        ):
            tree.heading(column, text=text, anchor=anchor)
            tree.column(
                column, width=width, anchor=anchor, stretch=column == "task"
            )
        for state, (_icon, _text, color) in theme.STEP_STYLES.items():
            tree.tag_configure(state, foreground=color)
        scroll = ttk.Scrollbar(holder, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._steps_tree = tree

    def _build_log_view(self, parent: tk.Frame) -> None:
        holder = tk.Frame(parent, bg=theme.LOG_BG)
        holder.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self._log_text = tk.Text(
            holder,
            wrap=tk.CHAR,
            height=18,
            state=tk.DISABLED,
            bg=theme.LOG_BG,
            fg=theme.LOG_FG,
            insertbackground="#ffffff",
            selectbackground="#334155",
            relief=tk.FLAT,
            font=theme.FONT_MONO,
            padx=8,
            pady=6,
        )
        log_scroll = ttk.Scrollbar(
            holder, orient=tk.VERTICAL, command=self._log_text.yview
        )
        self._log_text.configure(yscrollcommand=log_scroll.set)
        self._log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        for tag, color in theme.LOG_TAGS.items():
            self._log_text.tag_configure(tag, foreground=color)

    def _build_action_bar(self) -> None:
        bar = tk.Frame(
            self._content,
            bg=theme.SURFACE,
            highlightbackground=theme.BORDER,
            highlightthickness=1,
        )
        bar.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(0, 14))
        inner = tk.Frame(bar, bg=theme.SURFACE)
        inner.pack(fill=tk.X, padx=14, pady=10)

        self._stop_button = ttk.Button(
            inner,
            text="停止当前任务",
            command=self._stop_process,
            state=tk.DISABLED,
            style="Danger.TButton",
        )
        self._stop_button.pack(side=tk.RIGHT)

        actions = tk.Frame(inner, bg=theme.SURFACE)
        actions.pack(side=tk.RIGHT, padx=(0, 12))
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

        progress = tk.Frame(inner, bg=theme.SURFACE)
        progress.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._current_var = tk.StringVar(value="空闲")
        tk.Label(
            progress,
            textvariable=self._current_var,
            bg=theme.SURFACE,
            fg=theme.TEXT,
            font=theme.FONT_BOLD,
            anchor="w",
        ).pack(fill=tk.X)
        self._progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(
            progress,
            variable=self._progress_var,
            maximum=100,
            mode="determinate",
            style="Run.Horizontal.TProgressbar",
        ).pack(fill=tk.X, pady=(6, 0), padx=(0, 24))

    def _bind_shortcuts(self) -> None:
        self.root.bind("<F5>", lambda _event: self._run_serial())
        self.root.bind("<Control-s>", lambda _event: self._save_settings())
        self.root.bind("<Control-l>", lambda _event: self._clear_log())

    # ------------------------------------------------------------- 任务队列

    def _visible_specs(self) -> List[TaskSpec]:
        return [
            spec for spec in self._ordered_catalog if spec.key not in _HIDDEN_TASKS
        ]

    def _build_task_cards(self) -> None:
        """重建任务队列行，并刷新详情、摘要与执行计划。"""
        if self._queue_container is None:
            return
        for child in self._queue_container.winfo_children():
            child.destroy()
        self._card_enabled_vars.clear()
        self._task_rows.clear()
        visible = self._visible_specs()
        for index, spec in enumerate(visible, start=1):
            enabled_var = tk.BooleanVar(value=self._settings[spec.key].enabled)
            self._card_enabled_vars[spec.key] = enabled_var
            row = TaskRow(
                self._queue_container,
                spec=spec,
                index=index,
                enabled_var=enabled_var,
                on_toggle=lambda s=spec: self._on_card_enabled_changed(s),
                on_select=lambda s=spec: self._select_card(s),
                on_move=lambda direction, s=spec: self._move_task(s, direction),
            )
            row.pack(fill=tk.X, pady=1)
            row.set_meta(describe_settings(spec, self._settings[spec.key]))
            self._task_rows[spec.key] = row
        if self._selected_spec not in visible and visible:
            self._selected_spec = visible[0]
        self._highlight_selected()
        self._build_detail()
        self._refresh_selection_summary()

    def _highlight_selected(self) -> None:
        selected = self._selected_spec.key if self._selected_spec else None
        for key, row in self._task_rows.items():
            row.set_selected(key == selected)

    def _refresh_selection_summary(self) -> None:
        if not hasattr(self, "_selection_summary_var"):
            return
        enabled_specs = [
            spec
            for spec in self._visible_specs()
            if self._settings[spec.key].enabled
        ]
        if hasattr(self, "_queue_count_var"):
            self._queue_count_var.set(
                f"已选 {len(enabled_specs)}/{len(self._visible_specs())}"
            )
        try:
            plan = build_serial_plan(
                self._settings,
                self._catalog,
                order=[spec.key for spec in self._ordered_catalog],
            )
        except ValueError:
            self._selection_summary_var.set("任务参数需要检查")
            self._selection_detail_var.set("请修正无效数字后再运行")
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
        if not self._busy:
            self._show_plan_preview(plan)

    def _select_card(self, spec: TaskSpec) -> None:
        if self._selected_spec is spec:
            return
        self._selected_spec = spec
        self._highlight_selected()
        self._build_detail()

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
        except (tk.TclError, ValueError) as exc:
            self._detail_error_var.set(str(exc) or "请输入有效数字")
            return
        self._detail_error_var.set("")
        self._settings[spec.key].values[key] = value
        row = self._task_rows.get(spec.key)
        if row is not None:
            row.set_meta(describe_settings(spec, self._settings[spec.key]))
        self._save_settings(silent=True)
        self._refresh_selection_summary()
        if key == "cover_image":
            self._check_cover_field(spec)

    # ------------------------------------------------------------- 任务详情

    def _build_detail(self) -> None:
        body = self._detail_body
        if body is None:
            return
        for child in body.winfo_children():
            child.destroy()
        self._card_field_vars.clear()
        self._detail_run_button = None
        self._detail_error_var = tk.StringVar(value="")
        spec = self._selected_spec
        if spec is None:
            tk.Label(
                body, text="在左侧选择一个任务", bg=theme.SURFACE, fg=theme.MUTED
            ).pack(padx=14, pady=20)
            return
        settings = self._settings[spec.key]
        wrap = tk.Frame(body, bg=theme.SURFACE)
        wrap.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 12))

        title = tk.Frame(wrap, bg=theme.SURFACE)
        title.pack(fill=tk.X)
        tk.Label(
            title,
            text=spec.name,
            bg=theme.SURFACE,
            fg=theme.TEXT,
            font=(theme.FONT_FAMILY, 12, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            title,
            text="默认流程" if spec.default_enabled else "可选",
            bg="#ecfdf3" if spec.default_enabled else "#f2f4f7",
            fg=theme.SUCCESS if spec.default_enabled else theme.MUTED,
            font=theme.FONT_SMALL,
            padx=6,
            pady=1,
        ).pack(side=tk.LEFT, padx=(8, 0))
        tk.Label(
            wrap,
            text=spec.key,
            bg=theme.SURFACE,
            fg=theme.SUBTLE,
            font=theme.FONT_MONO,
            anchor="w",
        ).pack(fill=tk.X, pady=(2, 0))
        description = tk.Label(
            wrap,
            text=spec.description,
            bg=theme.SURFACE,
            fg=theme.MUTED,
            font=theme.FONT_UI,
            justify=tk.LEFT,
            anchor="w",
        )
        description.pack(fill=tk.X, pady=(6, 10))
        description.bind(
            "<Configure>",
            lambda event: description.configure(wraplength=max(event.width - 4, 120)),
        )

        form = tk.Frame(wrap, bg=theme.SURFACE)
        form.pack(fill=tk.X)
        enabled_var = self._card_enabled_vars.get(spec.key)
        if enabled_var is not None:
            tk.Label(
                form, text="加入今日队列", bg=theme.SURFACE, fg=theme.TEXT
            ).grid(row=0, column=0, sticky=tk.W, pady=3)
            tk.Checkbutton(
                form,
                variable=enabled_var,
                command=lambda: self._on_card_enabled_changed(spec),
                bg=theme.SURFACE,
                activebackground=theme.SURFACE,
                selectcolor=theme.SURFACE,
            ).grid(row=0, column=1, sticky=tk.W, pady=3)
        self._card_field_vars[spec.key] = {}
        row_index = 0
        for item in spec.fields:
            row_index += 1
            tk.Label(
                form, text=item.label, bg=theme.SURFACE, fg=theme.TEXT
            ).grid(row=row_index, column=0, sticky=tk.W, padx=(0, 12), pady=3)
            current = settings.value(spec, item.key)
            if item.kind in ("text", "file"):
                var: tk.Variable = tk.StringVar(value=str(current or ""))
                ttk.Entry(form, textvariable=var, width=20).grid(
                    row=row_index, column=1, columnspan=2, sticky=tk.W, pady=3
                )
                if item.kind == "file":
                    row_index += 1
                    self._cover_buttons(form, var).grid(
                        row=row_index, column=1, columnspan=2, sticky=tk.W
                    )
            elif item.kind == "bool":
                var = tk.BooleanVar(value=bool(current))
                tk.Checkbutton(
                    form,
                    variable=var,
                    bg=theme.SURFACE,
                    activebackground=theme.SURFACE,
                    selectcolor=theme.SURFACE,
                ).grid(row=row_index, column=1, sticky=tk.W, pady=3)
            else:
                var = tk.StringVar(
                    value=f"{current:g}" if isinstance(current, float) else str(current)
                )
                ttk.Spinbox(
                    form,
                    from_=item.minimum if item.minimum is not None else 0,
                    to=item.maximum if item.maximum is not None else 999999,
                    increment=item.step,
                    width=10,
                    textvariable=var,
                ).grid(row=row_index, column=1, sticky=tk.W, pady=3)
            var.trace_add(
                "write",
                lambda *_args, s=spec, key=item.key: self._on_card_field_changed(
                    s, key
                ),
            )
            hint = item.unit
            if item.minimum is not None and item.maximum is not None:
                hint = f"{hint}（{item.minimum:g}–{item.maximum:g}）".strip()
            if hint:
                tk.Label(
                    form, text=hint, bg=theme.SURFACE, fg=theme.SUBTLE, font=theme.FONT_SMALL
                ).grid(row=row_index, column=2, sticky=tk.W, padx=(8, 0))
            elif item.help:
                # 书名/封面等说明较长，单独占一行放在输入框下面。
                row_index += 1
                tk.Label(
                    form,
                    text=item.help,
                    bg=theme.SURFACE,
                    fg=theme.SUBTLE,
                    font=theme.FONT_SMALL,
                    justify=tk.LEFT,
                    anchor="w",
                    wraplength=190,
                ).grid(row=row_index, column=1, columnspan=2, sticky=tk.W, pady=(0, 3))
            self._card_field_vars[spec.key][item.key] = var
        if not spec.fields:
            tk.Label(
                wrap, text="此任务无可调参数", bg=theme.SURFACE, fg=theme.SUBTLE
            ).pack(anchor="w")

        tk.Label(
            wrap,
            textvariable=self._detail_error_var,
            bg=theme.SURFACE,
            fg=theme.DANGER,
            font=theme.FONT_UI,
            anchor="w",
        ).pack(fill=tk.X, pady=(6, 0))
        self._detail_run_button = ttk.Button(
            wrap,
            text="单独运行此任务",
            command=self._run_selected,
            style="Soft.TButton",
            state=tk.DISABLED if self._busy else tk.NORMAL,
        )
        self._detail_run_button.pack(anchor="w", pady=(6, 0))
        self._check_cover_field(spec)

    def _cover_buttons(self, parent: tk.Misc, var: tk.Variable) -> tk.Frame:
        frame = tk.Frame(parent, bg=theme.SURFACE)
        for text, command in (
            ("选择…", lambda: self._choose_cover_file(var)),
            ("截取…", lambda: self._open_cover_capture(var)),
            ("清除", lambda: var.set("")),
        ):
            ttk.Button(
                frame, text=text, command=command, style="Toolbar.TButton", width=6
            ).pack(side=tk.LEFT, padx=(0, 3))
        return frame

    def _check_cover_field(self, spec: TaskSpec) -> None:
        """封面参数不对不拦截保存，只在详情里提示。"""
        var = self._card_field_vars.get(spec.key, {}).get("cover_image")
        if var is None or not str(var.get()).strip():
            return
        problem = cover_tools.check_cover_file(Path(str(var.get()).strip()))
        if problem:
            self._detail_error_var.set(problem)

    def _choose_cover_file(self, var: tk.StringVar) -> None:
        path = filedialog.askopenfilename(
            title="选择听书封面（书架截图中裁出的封面）",
            initialdir=str(self.repo_root / "runtime" / cover_tools.COVER_DIR_NAME),
            filetypes=[("图片", "*.png *.jpg *.jpeg"), ("所有文件", "*.*")],
        )
        if path:
            var.set(path)

    def _open_cover_capture(self, var: tk.StringVar) -> None:
        """从模拟器当前画面框选封面：请先在模拟器里打开书架。"""
        config = self._require_config()
        if config is None:
            return
        if self._busy:
            messagebox.showwarning("截取封面", "任务运行中不能截图，请稍后再试")
            return
        CoverCaptureDialog(
            self.root,
            adb_path=config.machine.adb_path,
            address=config.machine.adb_address,
            runtime_dir=self.repo_root / "runtime",
            on_saved=lambda path: (
                var.set(str(path)),
                self._log(f"[封面] 已保存 {path}"),
            ),
        )

    # ------------------------------------------------------------- 执行计划视图

    def _show_plan_preview(self, plan: Sequence[TaskRunPlan]) -> None:
        if not hasattr(self, "_steps_tree"):
            return
        self._steps_title.configure(text="执行计划")
        self._steps_hint_var.set(f"共 {len(plan)} 步" if plan else "")
        tree = self._steps_tree
        tree.delete(*tree.get_children())
        for index, item in enumerate(plan, start=1):
            name = item.spec.name
            if item.repeat_total > 1:
                name += f"（{item.repeat_index}/{item.repeat_total}）"
            tree.insert(
                "",
                tk.END,
                values=(index, name, "○ 待执行", ""),
                tags=(FlowStepState.WAITING.value,),
            )

    def _refresh_steps_view(self) -> None:
        run = self._serial_run
        if run is None or not hasattr(self, "_steps_tree"):
            return
        self._steps_title.configure(text="本轮进度")
        self._steps_hint_var.set(f"run {run.run_id}")
        tree = self._steps_tree
        tree.delete(*tree.get_children())
        now = datetime.now(run.captured_at.tzinfo)
        current_item = None
        by_key = {spec.key: spec for spec in self._catalog}
        for index, step in enumerate(run.steps, start=1):
            icon, text, _color = theme.STEP_STYLES.get(
                step.state.value, ("?", step.state.value, theme.MUTED)
            )
            spec = by_key.get(step.snapshot.task_key)
            name = spec.name if spec is not None else step.snapshot.display_name
            if step.snapshot.repeat_total > 1:
                name += f"（{step.snapshot.repeat_index}/{step.snapshot.repeat_total}）"
            elapsed = ""
            if step.started_at is not None:
                end = step.ended_at or now
                elapsed = _format_duration((end - step.started_at).total_seconds())
            if step.exit_code not in (None, 0):
                text += f" ({step.exit_code})"
            item = tree.insert(
                "",
                tk.END,
                values=(index, name, f"{icon} {text}", elapsed),
                tags=(step.state.value,),
            )
            if step.state is FlowStepState.RUNNING:
                current_item = item
        if current_item is not None:
            tree.see(current_item)

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
            self._settings_panel.pack(
                fill=tk.X, padx=20, pady=(0, 10), before=self._main_area
            )
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
            self._set_config_state(f"加载失败：{path.name}", ok=False)
            self._log(f"[配置错误] {exc}")
            messagebox.showerror("配置错误", str(exc))
            return
        self._configured_adb_address = config.machine.adb_address
        self._config = self._with_device_override(config)
        self._config_var.set(str(path))
        self._set_config_state(path.name, ok=True)
        self._log(f"[配置] 已加载 {path}")
        for line in config.describe().splitlines():
            self._log("  " + line)
        if self._adb_override:
            self._log(f"[模拟器] 使用界面选择的地址 {self._adb_override}（覆盖配置里的 {config.machine.adb_address}）")
        self._refresh_device_selector()

    # ------------------------------------------------------------- 模拟器地址

    def _device_path(self) -> Path:
        return self.repo_root / "runtime" / "gui_device.json"

    def _with_device_override(self, config: AppConfig) -> AppConfig:
        if not self._adb_override or self._adb_override == config.machine.adb_address:
            return config
        machine = dataclasses.replace(config.machine, adb_address=self._adb_override)
        return dataclasses.replace(config, machine=machine)

    def _refresh_device_selector(self) -> None:
        if not hasattr(self, "_device_combo"):
            return
        values = candidate_addresses(
            self._configured_adb_address,
            self._scanned_devices,
            saved=self._adb_override,
            extra=mumu_default_addresses(),
        )
        self._device_combo.configure(values=values)
        current = self._adb_override or self._configured_adb_address
        self._device_var.set(current)
        if self._adb_override:
            hint = "界面选择（覆盖配置）"
        elif self._configured_adb_address:
            hint = "跟随配置文件"
        else:
            hint = "加载配置后可选择"
        if self._scanned_devices:
            hint += " · 已连接：" + describe_devices(self._scanned_devices)
        self._device_hint_var.set(hint)

    def _set_device_override(self, address: str) -> None:
        if self._busy:
            messagebox.showwarning("模拟器", "任务运行中不能切换模拟器，请先停止")
            self._refresh_device_selector()
            return
        try:
            save_device_address(self._device_path(), address)
        except (OSError, ValueError) as exc:
            self._log(f"[模拟器] 保存失败: {exc}")
            messagebox.showerror("模拟器", str(exc))
            self._refresh_device_selector()
            return
        self._adb_override = address
        if self._config is not None:
            base = self._config
            if base.machine.adb_address != self._configured_adb_address:
                base = dataclasses.replace(
                    base,
                    machine=dataclasses.replace(
                        base.machine, adb_address=self._configured_adb_address
                    ),
                )
            self._config = self._with_device_override(base)
        self._refresh_device_selector()

    def _apply_device(self) -> None:
        raw = self._device_var.get().strip()
        if raw == (self._adb_override or self._configured_adb_address):
            return
        if raw == self._configured_adb_address:
            self._reset_device()
            return
        try:
            address = validate_address(raw)
        except ValueError as exc:
            messagebox.showwarning("模拟器", str(exc))
            self._refresh_device_selector()
            return
        self._set_device_override(address)
        if self._adb_override == address:
            self._log(f"[模拟器] 已切换到 {address}；之后启动的任务都连接这个地址")

    def _reset_device(self) -> None:
        if not self._adb_override:
            self._refresh_device_selector()
            return
        self._set_device_override("")
        if not self._adb_override:
            self._log(
                "[模拟器] 已恢复跟随配置文件："
                + (self._configured_adb_address or "（配置未加载）")
            )

    def _scan_devices(self) -> None:
        """后台执行 adb connect（MuMu 默认端口）+ adb devices，刷新候选。"""
        config = self._require_config()
        if config is None or self._busy:
            return
        adb_path = config.machine.adb_path
        targets = candidate_addresses(
            self._configured_adb_address,
            saved=self._adb_override,
            extra=mumu_default_addresses(),
        )
        self._log("[模拟器] 正在扫描：" + "、".join(targets))
        self._device_hint_var.set("扫描中…")
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        def worker() -> None:
            for address in targets:
                if ":" not in address:
                    continue
                try:
                    subprocess.run(
                        list(build_adb_connect_command(adb_path, address)),
                        capture_output=True,
                        timeout=5,
                        check=False,
                        creationflags=creationflags,
                    )
                except (OSError, subprocess.SubprocessError):
                    pass
            try:
                result = subprocess.run(
                    list(build_adb_devices_command(adb_path)),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=10,
                    check=False,
                    creationflags=creationflags,
                )
                devices = parse_adb_devices(result.stdout)
            except (OSError, subprocess.SubprocessError) as exc:
                self._log_queue.put(f"[模拟器] adb devices 失败: {exc}")
                devices = []
            self.root.after(0, lambda: self._on_devices_scanned(devices))

        threading.Thread(target=worker, daemon=True).start()

    def _on_devices_scanned(self, devices: List[tuple]) -> None:
        self._scanned_devices = devices
        self._log("[模拟器] 扫描结果：" + describe_devices(devices))
        self._refresh_device_selector()

    def _set_config_state(self, text: str, *, ok: bool) -> None:
        self._config_state_var.set(("✓ " if ok else "✗ ") + text)
        self._config_state_label.configure(fg="#86efac" if ok else "#fca5a5")

    def _require_config(self) -> Optional[AppConfig]:
        if self._config is None:
            messagebox.showwarning("配置", "请先加载本机配置文件（侧边栏「设置」）")
            return None
        return self._config

    # ------------------------------------------------------------- 设置持久化

    def _settings_path(self) -> Path:
        return self.repo_root / "runtime" / "gui_tasks.json"

    def _load_task_settings_file(self) -> None:
        path = self._settings_path()
        self._settings = load_task_settings(path, self._catalog)
        self._ordered_catalog = load_task_order(path, self._catalog)
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
        visible_keys = [key for key in keys if key not in _HIDDEN_TASKS]
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
        command = [
            python,
            *python_args,
            str(self.repo_root / "scripts" / "dynamic_plan.py"),
            "--config",
            self._config_var.get(),
        ]
        self._start_process(
            command,
            status="读取奖励页并规划任务",
            on_finish=self._on_dynamic_plan_finished,
        )

    def _on_dynamic_plan_finished(self, code: int) -> None:
        if code == 0:
            self._load_task_settings_file()
            self._set_status("规划完成，请直接运行已选")
        else:
            self._set_status("规划未完成，请查看日志")

    # ------------------------------------------------------------- 模拟器

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
        self._set_status("等待设备就绪")

        def worker() -> None:
            from ..maa.adb import ensure_maa_ready

            ready, detail = ensure_maa_ready(
                config.machine.adb_path,
                config.machine.adb_address,
                package_name=config.machine.package_name,
                timeout=60.0,
            )
            self._log_queue.put(f"[ADB] {detail}")
            if not ready:
                self._log_queue.put("[ADB] 设备未就绪，启动任务时仍会再次重试。")
                self.root.after(0, lambda: self._set_status("设备未就绪"))
            elif launch_reader:
                self._log_queue.put("[一键启动] 设备已就绪，启动 QQ 阅读并清理弹窗")
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
        """快捷按钮：运行单个指定任务。"""
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
        self._run_task(spec.key)

    def _prepare_serial(self) -> bool:
        config = self._require_config()
        if config is None or self._busy:
            return False
        # 设置可在 GUI 启动后由规划器或其他进程更新；运行前读取磁盘最新版。
        self._load_task_settings_file()
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
        self._run_started_at = time.monotonic()
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
            self._after_step_finished()
            return
        index = self._serial_index + 1
        total = len(self._serial_plan)
        self._progress_var.set((index - 1) / total * 100)
        repeat = (
            f"（重复 {plan.repeat_index}/{plan.repeat_total}）"
            if plan.repeat_total > 1
            else ""
        )
        self._set_current(f"当前：{plan.spec.display_name} ({index}/{total})")
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
            self._stop_serial_run()
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
                f"{plan.spec.display_name} 失败 exit={code}（{describe_exit_code(code)}）"
            )
        self._progress_var.set(
            (self._serial_index + 1) / len(self._serial_plan) * 100
        )
        self._serial_index += 1
        self._after_step_finished()

    def _stop_serial_run(self) -> None:
        if (
            self._serial_run is not None
            and self._serial_run.state is FlowRunState.RUNNING
        ):
            self._serial_run.stop_by_user()
            self._save_serial_run()
        self._log("[串行] 已停止；当前任务已取消，后续任务已跳过")
        self._finish_serial()

    def _after_step_finished(self) -> None:
        """一项结束（完成或被跳过）后：验证码阻塞则停下，否则先做交接检查。"""
        run = self._serial_run
        if run is not None and run.state is FlowRunState.BLOCKED_BY_CAPTCHA:
            self._log("[串行] 验证码阻塞：后续任务不再启动。请人工处理验证码后重新运行。")
            self._finish_serial()
            return
        if self._serial_index >= len(self._serial_plan):
            self._finish_serial()
            return
        self._set_current(f"等待 {self._interval_seconds()} 秒后检查现场")
        self.root.after(self._interval_seconds() * 1000, self._start_handoff_check)

    def _start_handoff_check(self) -> None:
        """QQR-53：上一项留下的页面未经确认，不能直接交给下一项。"""
        if self._stopping:
            return
        config = self._require_config()
        run = self._serial_run
        if config is None or run is None:
            return
        plan = self._serial_plan[self._serial_index]
        report_path = handoff_report_path(Path(config.machine.record_dir), run)
        python_executable, python_args = self._python_launcher(config)
        command = build_handoff_command(
            python_executable,
            self.repo_root,
            Path(self._config_var.get()),
            plan.spec.key,
            report_path,
            python_args=python_args,
        )
        self._set_current(f"交接检查：准备启动 {plan.spec.display_name}")
        self._log(
            f"[交接] 启动 {plan.spec.display_name} 前确认现场\n"
            f"      {command_preview(command)}"
        )
        self._start_process(
            command,
            status=f"交接检查：{plan.spec.display_name}",
            on_finish=lambda code: self._on_handoff_finished(code, report_path),
        )

    def _on_handoff_finished(self, code: int, report_path: Path) -> None:
        if self._stopping:
            self._stop_serial_run()
            return
        run = self._serial_run
        if run is None or run.state is not FlowRunState.RUNNING:
            self._finish_serial()
            return
        plan = self._serial_plan[self._serial_index]
        report = load_handoff_report(report_path)
        started = apply_handoff(run, code, report)
        self._save_serial_run()
        if started is not None:
            self._log(f"[交接] 现场已确认（{report.get('reason', '书架')}），启动 {plan.spec.display_name}")
            self._start_next_task()
            return
        if run.state is FlowRunState.BLOCKED_BY_CAPTCHA:
            self._log("[交接] 发现验证码：不点击、不返回、不重启，后续任务全部停止，等待人工。")
            self._finish_serial()
            return
        skipped = run.steps[self._serial_index]
        self._log(f"[交接] 跳过 {plan.spec.display_name}：{skipped.reason}")
        self._serial_index += 1
        self._after_step_finished()

    def _save_serial_run(self) -> None:
        if self._serial_run is None or self._serial_recorder is None:
            return
        self._refresh_steps_view()
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
        self._run_started_at = None
        self._set_current("本轮运行结束")
        if run is None:
            self._set_status("串行执行结束")
            return
        counts = run.counts()
        success = counts[FlowStepState.SUCCEEDED.value]
        failed = counts[FlowStepState.FAILED.value]
        skipped = counts[FlowStepState.SKIPPED.value]
        if run.state is FlowRunState.CANCELLED:
            summary = f"已停止：成功 {success}，失败 {failed}，跳过 {skipped}"
        elif run.state is FlowRunState.BLOCKED_BY_CAPTCHA:
            summary = f"验证码阻塞，等待人工：成功 {success}，失败 {failed}，跳过 {skipped}"
        elif run.state is FlowRunState.COMPLETED_WITH_ERRORS:
            summary = f"完成但有错误：成功 {success}，失败 {failed}，跳过 {skipped}"
        else:
            summary = f"全部成功：{success} 项"
        self._progress_var.set(100)
        self._set_status(summary)
        self._refresh_steps_view()
        self._log(f"[串行] {summary}")
        if self._serial_record_path is not None:
            self._log(f"[串行记录] {self._serial_record_path}")

    def _set_current(self, text: str) -> None:
        self._current_text = text
        self._update_current_label()

    def _update_current_label(self) -> None:
        text = self._current_text
        if self._run_started_at is not None:
            elapsed = _format_duration(time.monotonic() - self._run_started_at)
            text = f"{text} · 已用 {elapsed}"
        self._current_var.set(text)

    def _tick_elapsed(self) -> None:
        if self._run_started_at is not None:
            self._update_current_label()
            if self._serial_run is not None and self._busy:
                self._refresh_steps_view()
        self.root.after(1000, self._tick_elapsed)

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
                env=child_env(os.environ, self._adb_override),
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
        if self._detail_run_button is not None:
            self._detail_run_button.configure(state=state)
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

    def _on_close(self) -> None:
        """关闭窗口时若仍有子进程在跑，先确认并终止，避免残留后台任务。"""
        if self._process is not None and self._process.poll() is None:
            if not messagebox.askyesno(
                "退出", "当前仍有任务在运行，退出将终止该任务。确定退出吗？"
            ):
                return
            self._stop_process()
        self.root.destroy()

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
        self._log_text.configure(state=tk.NORMAL)
        self._log_text.insert(
            tk.END, f"[{timestamp}] {message}\n", theme.log_tag(message)
        )
        lines = int(self._log_text.index("end-1c").split(".")[0])
        if lines > _LOG_MAX_LINES:
            self._log_text.delete("1.0", f"{lines - _LOG_MAX_LINES + 1}.0")
        if self._autoscroll_var.get():
            self._log_text.see(tk.END)
        self._log_text.configure(state=tk.DISABLED)

    def _set_status(self, text: str) -> None:
        self._status_var.set(text)
        self._status_dot.configure(fg=theme.status_color(text))


class CoverCaptureDialog:
    """截取模拟器当前画面，按住鼠标框选一本书的封面，保存为听书封面模板。"""

    _MAX_DISPLAY = (420, 760)

    def __init__(
        self,
        master: tk.Misc,
        *,
        adb_path: str,
        address: str,
        runtime_dir: Path,
        on_saved: Callable[[Path], object],
    ) -> None:
        self._adb_path = adb_path
        self._address = address
        self._runtime_dir = runtime_dir
        self._on_saved = on_saved
        self._png: Optional[bytes] = None
        self._size = (0, 0)
        self._scale = 1
        self._photo: Optional[tk.PhotoImage] = None
        self._start: Optional[tuple] = None
        self._end: Optional[tuple] = None
        self._rect: Optional[int] = None

        top = tk.Toplevel(master)
        top.title("截取听书封面")
        top.configure(bg=theme.SURFACE)
        top.transient(master)
        self._top = top
        tk.Label(
            top,
            text="先在模拟器里打开书架，点「重新截图」，再按住鼠标框住要听的书的封面。",
            bg=theme.SURFACE,
            fg=theme.MUTED,
            font=theme.FONT_UI,
            # 对话框宽度由 360px 的截图画布决定，说明文字要在画布宽度内换行。
            wraplength=340,
            justify=tk.LEFT,
        ).pack(fill=tk.X, padx=12, pady=(10, 6))
        self._canvas = tk.Canvas(
            top, width=360, height=640, bg="#111827", highlightthickness=0, cursor="crosshair"
        )
        self._canvas.pack(padx=12)
        self._canvas.bind("<ButtonPress-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_drag)
        self._status_var = tk.StringVar(value=f"正在截图 {address} …")
        tk.Label(
            top, textvariable=self._status_var, bg=theme.SURFACE, fg=theme.TEXT, font=theme.FONT_UI
        ).pack(fill=tk.X, padx=12, pady=6)
        buttons = tk.Frame(top, bg=theme.SURFACE)
        buttons.pack(fill=tk.X, padx=12, pady=(0, 12))
        ttk.Button(buttons, text="取消", command=top.destroy, style="Toolbar.TButton").pack(
            side=tk.RIGHT
        )
        ttk.Button(buttons, text="保存封面", command=self._save, style="Primary.TButton").pack(
            side=tk.RIGHT, padx=(0, 6)
        )
        ttk.Button(buttons, text="重新截图", command=self._capture, style="Toolbar.TButton").pack(
            side=tk.LEFT
        )
        self._capture()

    def _capture(self) -> None:
        self._status_var.set(f"正在截图 {self._address} …")

        def worker() -> None:
            try:
                png = cover_tools.capture_screen_png(self._adb_path, self._address)
                error = ""
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                png, error = None, str(exc)
            try:
                self._top.after(0, lambda: self._show(png, error))
            except tk.TclError:
                pass  # 对话框已关闭

        threading.Thread(target=worker, daemon=True).start()

    def _show(self, png: Optional[bytes], error: str) -> None:
        if png is None:
            self._status_var.set(f"截图失败：{error}")
            return
        try:
            size = cover_tools.image_size(png)
            photo = tk.PhotoImage(data=base64.b64encode(png).decode("ascii"))
        except (ValueError, ImportError, tk.TclError) as exc:
            self._status_var.set(f"截图无法显示：{exc}")
            return
        self._png, self._size = png, size
        self._scale = cover_tools.display_scale(size[0], size[1], *self._MAX_DISPLAY)
        self._photo = photo.subsample(self._scale) if self._scale > 1 else photo
        self._canvas.configure(
            width=self._photo.width(), height=self._photo.height()
        )
        self._canvas.delete("all")
        self._canvas.create_image(0, 0, image=self._photo, anchor=tk.NW)
        self._rect = None
        self._start = self._end = None
        self._status_var.set(f"截图 {size[0]}×{size[1]}，请框选封面")

    def _on_press(self, event: tk.Event) -> None:
        if self._png is None:
            return
        self._start = self._end = (event.x, event.y)
        if self._rect is not None:
            self._canvas.delete(self._rect)
        self._rect = self._canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="#f97316", width=2
        )

    def _on_drag(self, event: tk.Event) -> None:
        if self._start is None or self._rect is None:
            return
        self._end = (event.x, event.y)
        self._canvas.coords(self._rect, *self._start, *self._end)
        try:
            box = cover_tools.crop_box(self._start, self._end, self._scale, self._size)
            self._status_var.set(f"选区 x={box[0]} y={box[1]} {box[2]}×{box[3]}")
        except ValueError as exc:
            self._status_var.set(str(exc))

    def _save(self) -> None:
        if self._png is None or self._start is None or self._end is None:
            self._status_var.set("请先截图并框选封面")
            return
        try:
            box = cover_tools.crop_box(self._start, self._end, self._scale, self._size)
            path = cover_tools.save_cover(
                self._runtime_dir, cover_tools.crop_png(self._png, box)
            )
        except (OSError, ValueError, ImportError) as exc:
            self._status_var.set(f"保存失败：{exc}")
            return
        self._on_saved(path)
        self._top.destroy()


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


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
