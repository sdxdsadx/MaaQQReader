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

BG = "#f3f5f9"
CARD = "#ffffff"
TEXT = "#1f2937"
MUTED = "#6b7280"
ACCENT = "#2563eb"
ACCENT_ACTIVE = "#1d4ed8"
DANGER = "#dc2626"
SUCCESS = "#16a34a"
WARNING = "#d97706"
BORDER = "#d7dde8"
LOG_BG = "#0f172a"
LOG_FG = "#e2e8f0"
FONT_UI = ("Microsoft YaHei UI", 9)
FONT_TITLE = ("Microsoft YaHei UI", 12, "bold")
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
        self._serial_failures = 0

        self._build_ui()
        self._load_task_settings_file()
        if config_path is not None:
            self._load_config(Path(config_path))

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        self.root.title("QQReader 每日任务控制台")
        self.root.geometry("1240x800")
        self.root.minsize(1040, 660)
        self.root.configure(bg=BG)
        self._configure_styles()
        self._build_header()
        self._build_toolbar()
        self._build_main_panes()
        self._build_action_bar()
        self.root.after(100, self._drain_log_queue)
        self._log("GUI 已启动。左侧勾选任务，右侧设置参数，点击底部「串行执行」。")

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
        style.configure("Toolbar.TButton", padding=(8, 5))
        style.configure(
            "Primary.TButton",
            font=("Microsoft YaHei UI", 10, "bold"),
            foreground="#ffffff",
            background=ACCENT,
            padding=(18, 8),
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
        header = tk.Frame(self.root, bg=BG, padx=14, pady=10)
        header.pack(fill=tk.X)
        ttk.Label(
            header, text="QQReader 每日任务控制台", style="Title.TLabel"
        ).pack(side=tk.LEFT)
        right = ttk.Frame(header)
        right.pack(side=tk.RIGHT)
        ttk.Label(right, text="配置文件").pack(side=tk.LEFT)
        self._config_var = tk.StringVar()
        ttk.Entry(right, textvariable=self._config_var, width=56).pack(
            side=tk.LEFT, padx=(6, 6)
        )
        ttk.Button(
            right, text="选择…", command=self._choose_config, style="Toolbar.TButton"
        ).pack(side=tk.LEFT)
        ttk.Button(
            right, text="加载", command=self._load_config_from_entry, style="Toolbar.TButton"
        ).pack(side=tk.LEFT, padx=(6, 0))

    def _build_toolbar(self) -> None:
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill=tk.X, padx=14, pady=(0, 8))
        self._action_buttons: List[ttk.Button] = []
        self._launch_button = ttk.Button(
            bar,
            text="启动模拟器",
            command=self._launch_emulator,
            style="Toolbar.TButton",
        )
        self._launch_button.pack(side=tk.LEFT)
        self._action_buttons.append(self._launch_button)

        for text, command in (
            ("启动QQ阅读", lambda: self._run_task("LaunchQQReader")),
            ("识别检查", lambda: self._run_task("SmokeTest")),
            ("每日默认", lambda: self._apply_preset(True)),
            ("1分钟试运行", lambda: self._apply_preset(False)),
            ("保存设置", self._save_settings),
            ("打开记录目录", self._open_record_dir),
        ):
            button = ttk.Button(
                bar, text=text, command=command, style="Toolbar.TButton"
            )
            button.pack(side=tk.LEFT, padx=(6, 0))
            self._action_buttons.append(button)

    def _build_main_panes(self) -> None:
        paned = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 6))

        left = tk.Frame(paned, bg=BG)
        paned.add(left, weight=3)
        left_header = tk.Frame(left, bg=BG)
        left_header.pack(fill=tk.X, padx=4, pady=(0, 6))
        tk.Label(
            left_header,
            text="任务列表",
            bg=BG,
            fg=TEXT,
            font=("Microsoft YaHei UI", 11, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            left_header,
            text="勾选任务并直接修改参数",
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
        paned.add(right, weight=2)
        log_header = tk.Frame(right, bg=CARD)
        log_header.pack(fill=tk.X, padx=12, pady=(8, 4))
        tk.Label(
            log_header,
            text="实时日志",
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
        bar.pack(fill=tk.X, padx=14, pady=(4, 12))
        self._serial_button = ttk.Button(
            bar,
            text="串行执行",
            command=self._run_serial,
            style="Primary.TButton",
        )
        self._serial_button.pack(side=tk.LEFT)
        self._action_buttons.append(self._serial_button)
        self._selected_button = ttk.Button(
            bar,
            text="运行选中任务",
            command=self._run_selected,
            style="Toolbar.TButton",
        )
        self._selected_button.pack(side=tk.LEFT, padx=(8, 0))
        self._action_buttons.append(self._selected_button)
        self._stop_button = ttk.Button(
            bar,
            text="停止",
            command=self._stop_process,
            state=tk.DISABLED,
            style="Danger.TButton",
        )
        self._stop_button.pack(side=tk.LEFT, padx=(8, 0))

        right = tk.Frame(bar, bg=BG)
        right.pack(side=tk.RIGHT)
        ttk.Label(right, text="任务间隔").pack(side=tk.LEFT)
        self._interval_var = tk.StringVar(value="3")
        ttk.Spinbox(
            right,
            from_=0,
            to=120,
            increment=1,
            width=5,
            textvariable=self._interval_var,
        ).pack(side=tk.LEFT, padx=(6, 2))
        ttk.Label(right, text="秒").pack(side=tk.LEFT)
        ttk.Label(right, text="状态：").pack(side=tk.LEFT, padx=(18, 0))
        self._status_dot = tk.Label(
            right, text="●", bg=BG, fg=MUTED, font=("Segoe UI", 10)
        )
        self._status_dot.pack(side=tk.LEFT)
        self._status_var = tk.StringVar(value="未运行")
        tk.Label(
            right,
            textvariable=self._status_var,
            bg=BG,
            fg=TEXT,
            font=FONT_UI,
        ).pack(side=tk.LEFT, padx=(4, 0))
        self._current_var = tk.StringVar(value="")
        tk.Label(
            right,
            textvariable=self._current_var,
            bg=BG,
            fg=MUTED,
            font=FONT_UI,
        ).pack(side=tk.LEFT, padx=(12, 0))

    # ------------------------------------------------------------- 任务树

    def _build_task_cards(self) -> None:
        if self._cards_container is None:
            return
        for child in self._cards_container.winfo_children():
            child.destroy()
        self._card_enabled_vars.clear()
        self._card_field_vars.clear()
        groups: Dict[str, List[TaskSpec]] = {}
        for spec in self._ordered_catalog:
            groups.setdefault(spec.group, []).append(spec)
        for group, specs in groups.items():
            self._build_group_header(group, len(specs))
            for spec in specs:
                self._build_task_card(spec)
        if self._selected_spec is None and self._ordered_catalog:
            self._selected_spec = self._ordered_catalog[0]
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

    def _build_task_card(self, spec: TaskSpec) -> None:
        settings = self._settings[spec.key]
        card = tk.Frame(
            self._cards_container,
            bg=CARD,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        card.pack(fill=tk.X, padx=4, pady=4)

        top = tk.Frame(card, bg=CARD)
        top.pack(fill=tk.X, padx=12, pady=(10, 2))
        enabled_var = tk.BooleanVar(value=settings.enabled)
        self._card_enabled_vars[spec.key] = enabled_var
        tk.Checkbutton(
            top,
            text=spec.display_name,
            variable=enabled_var,
            bg=CARD,
            fg=TEXT,
            activebackground=CARD,
            selectcolor=CARD,
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
            command=lambda s=spec: self._on_card_enabled_changed(s),
        ).pack(side=tk.LEFT)
        if not spec.implemented:
            tk.Label(
                top,
                text="旧流程",
                bg="#fef3c7",
                fg=WARNING,
                font=("Microsoft YaHei UI", 8, "bold"),
                padx=6,
                pady=1,
            ).pack(side=tk.LEFT, padx=(8, 0))
        order = tk.Frame(top, bg=CARD)
        order.pack(side=tk.RIGHT)
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
            wraplength=620,
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, padx=12, pady=(0, 6))

        fields = tk.Frame(card, bg=CARD)
        fields.pack(fill=tk.X, padx=12, pady=(0, 10))
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
        try:
            index = keys.index(spec.key)
        except ValueError:
            return
        target = index + direction
        if target < 0 or target >= len(keys):
            return
        keys[index], keys[target] = keys[target], keys[index]
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
        for spec in self._catalog:
            settings = self._settings[spec.key]
            for item in spec.fields:
                if item.key == "count":
                    settings.values["count"] = item.default if formal else 1
                elif item.key == "minutes":
                    settings.values["minutes"] = item.default if formal else 1
                elif item.key == "duration_minutes":
                    settings.values["duration_minutes"] = (
                        item.default if formal else 1
                    )
        self._build_task_cards()
        self._save_settings(silent=True)
        self._log(
            "[预设] 已应用每日默认配置"
            if formal
            else "[预设] 已应用 1 分钟试运行配置"
        )

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

    def _on_emulator_finished(self, code: int) -> None:
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

        threading.Thread(target=worker, daemon=True).start()

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
        self._serial_index = 0
        self._serial_failures = 0
        self._stopping = False
        self._log(f"[串行] 共 {len(self._serial_plan)} 个任务，按顺序执行")
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
            self._serial_index += 1
            self._serial_failures += 1
            self.root.after(500, self._start_next_task)
            return
        index = self._serial_index + 1
        total = len(self._serial_plan)
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
            self._log("[串行] 已停止")
            return
        plan = self._serial_plan[self._serial_index]
        if code == 0:
            self._log(
                f"[{self._serial_index + 1}/{len(self._serial_plan)}] "
                f"{plan.spec.display_name} 成功"
            )
        else:
            self._serial_failures += 1
            self._log(
                f"[{self._serial_index + 1}/{len(self._serial_plan)}] "
                f"{plan.spec.display_name} 失败 exit={code}"
            )
        self._serial_index += 1
        self.root.after(self._interval_seconds() * 1000, self._start_next_task)

    def _interval_seconds(self) -> int:
        try:
            return max(0, int(float(self._interval_var.get())))
        except ValueError:
            return 0

    def _finish_serial(self) -> None:
        success = len(self._serial_plan) - self._serial_failures
        self._current_var.set("")
        if self._serial_failures:
            self._set_status(
                f"串行完成：成功 {success}，失败 {self._serial_failures}"
            )
        else:
            self._set_status(f"串行完成：成功 {success}")
        self._log(f"[串行] 完成，成功 {success}，失败 {self._serial_failures}")

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
        self._serial_plan = []
        self._serial_index = 0
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
        self._set_status("已停止")

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
