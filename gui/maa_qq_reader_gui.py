from __future__ import annotations

import json
import locale
import os
import queue
import re
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk


APP_TITLE = "QQ 阅读每日任务"
BG = "#F4F7FB"
CARD = "#FFFFFF"
TEXT = "#172033"
MUTED = "#687386"
PRIMARY = "#2878FF"
PRIMARY_DARK = "#155FD1"
SUCCESS = "#16A36A"
DANGER = "#E24B4B"
BORDER = "#DDE4EE"


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


ROOT_DIR = project_root()
DEV_DIR = ROOT_DIR / "dev"
CLI_PATH = DEV_DIR / "MaaPiCli.exe"
RUNNER_PY = ROOT_DIR / ".venv-captcha" / "Scripts" / "python.exe"
RUNNER_SCRIPT = ROOT_DIR / "tools" / "run_maa_ad.py"
SOLVER_SCRIPT = ROOT_DIR / "tools" / "captcha_solver.py"
AD_LOCATOR_SCRIPT = ROOT_DIR / "tools" / "ad_locator.py"
SLIDE_SOLVER_SCRIPT = ROOT_DIR / "tools" / "slide_captcha_solver.py"
INTERFACE_PATH = DEV_DIR / "interface.json"
CONFIG_PATH = DEV_DIR / "config" / "maa_pi_config.json"
PIPELINE_PATH = DEV_DIR / "resource" / "pipeline" / "qq_reader_trial.json"
GUI_SETTINGS_PATH = DEV_DIR / "config" / "maa_gui_config.json"
MAA_LOG_PATH = DEV_DIR / "debug" / "maafw.log"
MUMU_PATH = Path("D:/Program Files/Netease/MuMu Player 12/shell/MuMuPlayer.exe")
MUMU_MANAGER_PATH = Path("D:/Program Files/Netease/MuMu Player 12/shell/MuMuManager.exe")
ADB_PATH = Path("D:/Program Files/Netease/MuMu Player 12/shell/adb.exe")
ADB_ADDRESS = "127.0.0.1:16385"
# MaaPiCli re-discovers the selected device before creating its controller and
# uses the discovered name to carry MuMu's extra input/screencap configuration.
# Keeping this name in the generated config prevents it from falling back to
# an empty native-controller config when the same ADB endpoint is shared by
# more than one emulator integration.
ADB_DEVICE_NAME = "碧蓝航线-MuMuPlayer v4"
PLAN_SCAN_ENTRY = "DailyPlanScan"
CLAIM_REWARDS_ENTRY = "ClaimOneReward"
CLAIM_GAME_REWARD_ENTRY = "ClaimGameReward"
FINAL_REWARD_EVIDENCE_ENTRY = "DailyFinalRewardEvidence"
FINAL_REWARD_SCREENSHOT_PATH = Path(os.environ.get(
    "GAMEFLOW_QQ_REWARD_SCREENSHOT",
    r"G:\project_I\logs\qq_reader_final.png",
))
# QQ 阅读正文页启用 FLAG_SECURE，不能把“自动阅读”按钮是否响应作为
# 唯一成功条件。每段停留不超过 15 分钟，返回书架后重新进书，确保即使
# 自动翻页失效也能稳定累计在线阅读时长。
DIRECT_READING_DWELL_SEGMENT_MINUTES = 15


def adb_environment() -> dict[str, str]:
    """Use the same ADB server as GameFlow/MuMu (port 5038 by default)."""
    environment = os.environ.copy()
    environment["ANDROID_ADB_SERVER_PORT"] = environment.get(
        "ANDROID_ADB_SERVER_PORT", "5038")
    return environment


def refresh_adb_address() -> str:
    """Read MuMu 0's current ADB port instead of assuming it is stable."""
    global ADB_ADDRESS
    if not MUMU_MANAGER_PATH.exists():
        return ADB_ADDRESS
    try:
        completed = subprocess.run(
            [str(MUMU_MANAGER_PATH), "info", "--vmindex", "0"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        payload = json.loads(completed.stdout.decode("utf-8", errors="replace"))
        host = str(payload.get("adb_host_ip") or "127.0.0.1")
        port = int(payload.get("adb_port") or 0)
        if completed.returncode == 0 and 0 < port < 65536:
            candidate = f"{host}:{port}"
            # During MuMu startup info may expose the next port before the
            # transport is attached. Keep an online endpoint when one exists.
            env = adb_environment()
            listed = subprocess.run(
                [str(ADB_PATH), "devices"], stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=8, env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            rows = listed.stdout.decode(locale.getpreferredencoding(False), errors="replace").splitlines()
            online = {row.split()[0] for row in rows[1:]
                      if len(row.split()) >= 2 and row.split()[1] == "device"
                      and row.split()[0].startswith("127.0.0.1:")}
            ADB_ADDRESS = candidate if candidate in online or not online else next(
                (value for value in ("127.0.0.1:16385", "127.0.0.1:16384") if value in online),
                candidate,
            )
    except (OSError, subprocess.SubprocessError, ValueError, TypeError,
            json.JSONDecodeError):
        pass
    return ADB_ADDRESS


LAUNCH_QQ_TASK = "00 启动 QQ 阅读并关闭开屏弹窗"
TIMED_TASKS = {
    "01 ": "ReadingWaitOneMinute",
    "02 ": "AudiobookWaitOneMinute",
    "03 ": "GameWaitOneMinute",
}
FORMAL_MINUTES = {
    "01 ": 35,
    "02 ": 35,
    "03 ": 25,
}
# Maa's built-in timed game/listening entries intentionally sleep for a long
# period.  Keep a separate heartbeat in the framework log so GameFlow's
# five-minute no-log watchdog can distinguish a deliberate dwell from a hung
# controller.
LONG_DWELL_ENTRIES = {
    "DailyAudiobookFlow": "每日听书",
    "DailyGameFlow": "每日游戏",
}
GUI_STATUS_LOG_PATH = MAA_LOG_PATH.parent / "gameflow_gui_status.log"


def append_gui_status(message: str) -> None:
    """Write supervisor markers without touching MaaFramework's active log."""
    GUI_STATUS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with GUI_STATUS_LOG_PATH.open("a", encoding="utf-8") as status_log:
        status_log.write(
            f"[{datetime.now():%Y-%m-%d %H:%M:%S.%f}] {message}\n")
DEFAULT_COUNTS = {
    "01 ": 2,
    "02 ": 1,
    "03 ": 1,
    "04 ": 1,
    "05 ": 1,
    "06 ": 1,
}


class MaaQQReaderGui:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1180x760")
        self.root.minsize(1050, 680)
        self.root.configure(bg=BG)

        self.process: subprocess.Popen[str] | None = None
        self.original_config: bytes | None = None
        self.original_pipeline: bytes | None = None
        self.messages: queue.Queue[tuple[str, str]] = queue.Queue()
        self.task_rows: list[dict[str, object]] = []
        self.is_running = False
        self.dynamic_planning_var = tk.BooleanVar(value=True)
        self.run_failed = False
        self.captcha_notified = False
        self.captcha_solver_running = False
        self.ad_locator_running = False
        self.ad_locator_last_at = 0.0
        self.ad_locator_attempts = 0
        self.slide_solver_running = False
        self.slide_solver_last_at = 0.0
        self.slide_solver_attempts = 0
        self.stop_requested = threading.Event()

        self._configure_styles()
        self._build_ui()
        self._load_tasks()
        self._poll_messages()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD)
        style.configure(
            "Primary.TButton",
            background=PRIMARY,
            foreground="white",
            borderwidth=0,
            padding=(22, 11),
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        style.map("Primary.TButton", background=[("active", PRIMARY_DARK), ("disabled", "#A9C5F5")])
        style.configure(
            "Secondary.TButton",
            background="#EAF1FF",
            foreground=PRIMARY_DARK,
            borderwidth=0,
            padding=(16, 9),
            font=("Microsoft YaHei UI", 9),
        )
        style.map("Secondary.TButton", background=[("active", "#DCE8FF")])
        style.configure(
            "Danger.TButton",
            background="#FDECEC",
            foreground=DANGER,
            borderwidth=0,
            padding=(22, 11),
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        style.map("Danger.TButton", background=[("active", "#FADDDD"), ("disabled", "#F5EFEF")])
        style.configure(
            "Task.TCheckbutton",
            background=CARD,
            foreground=TEXT,
            font=("Microsoft YaHei UI", 10),
            padding=(4, 7),
        )
        style.map("Task.TCheckbutton", background=[("active", CARD)])

    def _build_ui(self) -> None:
        outer = tk.Frame(self.root, bg=BG)
        outer.pack(fill="both", expand=True, padx=26, pady=22)

        header = tk.Frame(outer, bg=BG)
        header.pack(fill="x", pady=(0, 16))
        tk.Label(
            header,
            text=APP_TITLE,
            bg=BG,
            fg=TEXT,
            font=("Microsoft YaHei UI", 20, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="MuMu 模拟器 · 可调整时间、次数和顺序 · 所有任务串行执行",
            bg=BG,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w", pady=(5, 0))

        connection = tk.Frame(outer, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        connection.pack(fill="x", pady=(0, 14))
        connection_inner = tk.Frame(connection, bg=CARD)
        connection_inner.pack(fill="x", padx=18, pady=14)
        self.status_dot = tk.Label(connection_inner, text="●", bg=CARD, fg="#AAB3C2", font=("Arial", 13))
        self.status_dot.pack(side="left")
        self.connection_label = tk.Label(
            connection_inner,
            text="模拟器连接尚未检查",
            bg=CARD,
            fg=TEXT,
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        self.connection_label.pack(side="left", padx=(7, 0))
        self.cli_button = ttk.Button(connection_inner, text="打开 CLI", style="Secondary.TButton", command=self._open_cli)
        self.cli_button.pack(side="right")
        ttk.Button(connection_inner, text="检查连接", style="Secondary.TButton", command=self._check_connection).pack(
            side="right", padx=(0, 10)
        )
        self.qq_button = ttk.Button(connection_inner, text="启动 QQ 阅读", style="Secondary.TButton", command=self._start_qq_reader)
        self.qq_button.pack(side="right", padx=(0, 10))
        self.emulator_button = ttk.Button(connection_inner, text="启动模拟器", style="Secondary.TButton", command=self._start_emulator)
        self.emulator_button.pack(side="right", padx=(0, 10))

        content = tk.Frame(outer, bg=BG)
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=0, minsize=535)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        task_card = tk.Frame(content, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        task_card.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        task_header = tk.Frame(task_card, bg=CARD)
        task_header.pack(fill="x", padx=18, pady=(16, 8))
        tk.Label(
            task_header,
            text="任务编排",
            bg=CARD,
            fg=TEXT,
            font=("Microsoft YaHei UI", 12, "bold"),
        ).pack(side="left")
        tk.Button(
            task_header,
            text="全选",
            bg=CARD,
            fg=PRIMARY,
            activebackground=CARD,
            activeforeground=PRIMARY_DARK,
            bd=0,
            font=("Microsoft YaHei UI", 9),
            cursor="hand2",
            command=lambda: self._set_all(True),
        ).pack(side="right")
        tk.Button(
            task_header,
            text="清空",
            bg=CARD,
            fg=MUTED,
            activebackground=CARD,
            bd=0,
            font=("Microsoft YaHei UI", 9),
            cursor="hand2",
            command=lambda: self._set_all(False),
        ).pack(side="right", padx=(0, 10))
        tk.Button(
            task_header,
            text="1分钟×1",
            bg=CARD,
            fg=PRIMARY,
            activebackground=CARD,
            activeforeground=PRIMARY_DARK,
            bd=0,
            font=("Microsoft YaHei UI", 9),
            cursor="hand2",
            command=lambda: self._apply_timing_preset(False),
        ).pack(side="right", padx=(0, 10))
        tk.Button(
            task_header,
            text="每日默认配置",
            bg=CARD,
            fg=PRIMARY,
            activebackground=CARD,
            activeforeground=PRIMARY_DARK,
            bd=0,
            font=("Microsoft YaHei UI", 9),
            cursor="hand2",
            command=lambda: self._apply_timing_preset(True),
        ).pack(side="right", padx=(0, 10))
        tk.Checkbutton(
            task_header,
            text="启用动态规划",
            variable=self.dynamic_planning_var,
            bg=CARD,
            fg=TEXT,
            activebackground=CARD,
            activeforeground=TEXT,
            bd=0,
            font=("Microsoft YaHei UI", 9),
            cursor="hand2",
            command=self._save_gui_settings,
        ).pack(side="right", padx=(0, 12))
        columns = tk.Frame(task_card, bg="#F7F9FC")
        columns.pack(fill="x", padx=16, pady=(2, 5))
        tk.Label(columns, text="任务", bg="#F7F9FC", fg=MUTED, width=29, anchor="w", font=("Microsoft YaHei UI", 8)).pack(side="left", padx=(6, 0), pady=5)
        tk.Label(columns, text="单次分钟", bg="#F7F9FC", fg=MUTED, width=7, font=("Microsoft YaHei UI", 8)).pack(side="left")
        tk.Label(columns, text="重复次数", bg="#F7F9FC", fg=MUTED, width=7, font=("Microsoft YaHei UI", 8)).pack(side="left")
        tk.Label(columns, text="顺序", bg="#F7F9FC", fg=MUTED, width=7, font=("Microsoft YaHei UI", 8)).pack(side="left")
        self.task_frame = ttk.Frame(task_card, style="Card.TFrame")
        self.task_frame.pack(fill="both", expand=True, padx=15, pady=(0, 8))
        tk.Label(
            task_card,
            text="单次分钟是等待时长；重复次数会把同一任务连续执行多遍。",
            bg=CARD,
            fg=MUTED,
            font=("Microsoft YaHei UI", 8),
        ).pack(anchor="w", padx=19, pady=(0, 14))

        log_card = tk.Frame(content, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        log_card.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        log_header = tk.Frame(log_card, bg=CARD)
        log_header.pack(fill="x", padx=18, pady=(16, 8))
        tk.Label(
            log_header,
            text="运行日志",
            bg=CARD,
            fg=TEXT,
            font=("Microsoft YaHei UI", 12, "bold"),
        ).pack(side="left")
        self.run_state_label = tk.Label(
            log_header,
            text="空闲",
            bg="#EEF2F7",
            fg=MUTED,
            padx=10,
            pady=3,
            font=("Microsoft YaHei UI", 8, "bold"),
        )
        self.run_state_label.pack(side="right")
        log_container = tk.Frame(log_card, bg=CARD)
        log_container.pack(fill="both", expand=True, padx=18, pady=(0, 16))
        scrollbar = ttk.Scrollbar(log_container)
        scrollbar.pack(side="right", fill="y")
        self.log_text = tk.Text(
            log_container,
            wrap="word",
            bg="#101826",
            fg="#DDE8F7",
            insertbackground="white",
            relief="flat",
            padx=12,
            pady=10,
            font=("Cascadia Mono", 9),
            yscrollcommand=scrollbar.set,
        )
        self.log_text.pack(fill="both", expand=True)
        scrollbar.configure(command=self.log_text.yview)
        self.log_text.configure(state="disabled")

        controls = tk.Frame(outer, bg=BG)
        content.pack_forget()
        controls.pack(side="bottom", fill="x", pady=(16, 0))
        content.pack(fill="both", expand=True)
        self.start_button = ttk.Button(controls, text="开始执行所选任务", style="Primary.TButton", command=self._start)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(controls, text="停止任务", style="Danger.TButton", command=self._stop, state="disabled")
        self.stop_button.pack(side="left", padx=(10, 0))
        self.summary_label = tk.Label(
            controls,
            text="请选择至少一个任务",
            bg=BG,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
        )
        self.summary_label.pack(side="right")

    def _load_tasks(self) -> None:
        try:
            data = json.loads(INTERFACE_PATH.read_text(encoding="utf-8"))
            tasks = [item["name"] for item in data.get("task", [])]
        except Exception as exc:
            self._append_log(f"读取任务列表失败：{exc}")
            tasks = []
        saved: dict[str, dict[str, object]] = {}
        saved_order: list[str] = []
        if GUI_SETTINGS_PATH.exists():
            try:
                settings = json.loads(GUI_SETTINGS_PATH.read_text(encoding="utf-8"))
                saved_order = [item["name"] for item in settings.get("tasks", [])]
                saved = {item["name"]: item for item in settings.get("tasks", [])}
                self.dynamic_planning_var.set(bool(settings.get("dynamic_planning", True)))
            except Exception as exc:
                self._append_log(f"界面设置读取失败，已使用默认值：{exc}")

        order_index = {name: index for index, name in enumerate(saved_order)}
        default_order = {name: index for index, name in enumerate(tasks)}
        tasks.sort(
            key=lambda name: order_index[name]
            if name in order_index
            else (-1 if name == LAUNCH_QQ_TASK else len(order_index) + default_order[name])
        )
        for name in tasks:
            item = saved.get(name, {})
            enabled_var = tk.BooleanVar(value=bool(item.get("enabled", not name.startswith("00 "))))
            count_var = tk.IntVar(value=int(item.get("count", self._default_count(name))))
            minute_var = (
                tk.IntVar(value=int(item.get("minutes", self._default_minutes(name))))
                if self._timing_node(name)
                else None
            )
            enabled_var.trace_add("write", lambda *_: self._update_selection_summary())
            count_var.trace_add("write", lambda *_: self._update_selection_summary())
            self.task_rows.append(
                {
                    "name": name,
                    "enabled_var": enabled_var,
                    "count_var": count_var,
                    "minute_var": minute_var,
                }
            )
        self._render_task_rows()
        self._update_selection_summary()

    def _set_all(self, value: bool) -> None:
        if self.is_running:
            return
        for row in self.task_rows:
            row["enabled_var"].set(value)

    def _apply_timing_preset(self, formal: bool) -> None:
        if self.is_running:
            return
        for row in self.task_rows:
            row["count_var"].set(self._default_count(str(row["name"])) if formal else 1)
            minute_var = row["minute_var"]
            if minute_var is None:
                continue
            minutes = self._default_minutes(str(row["name"])) if formal else 1
            minute_var.set(minutes)
        self._save_gui_settings()
        self._append_log(
            "已应用每日默认配置：自动阅读 2×35 分钟、听书 35 分钟、游戏 25 分钟。"
            if formal
            else "已应用 1 分钟试运行且每项只执行 1 次。"
        )

    def _default_count(self, name: str) -> int:
        for prefix, count in DEFAULT_COUNTS.items():
            if name.startswith(prefix):
                return count
        return 1

    def _default_minutes(self, name: str) -> int:
        for prefix, minutes in FORMAL_MINUTES.items():
            if name.startswith(prefix):
                return minutes
        return 1

    def _timing_node(self, name: str) -> str | None:
        for prefix, node in TIMED_TASKS.items():
            if name.startswith(prefix):
                return node
        return None

    def _display_name(self, name: str) -> str:
        if name == LAUNCH_QQ_TASK:
            return "00 启动 QQ 阅读（关闭弹窗）"
        if name.startswith("04 "):
            return "04 每日广告（自动至 12/12）"
        if name.startswith("05 "):
            return "05 外部应用（大众点评 + 百度地图）"
        if name.startswith("06 "):
            return "06 等级页广告（赠币 + 积分）"
        return name.replace(" 1 分钟试运行", "")

    def _render_task_rows(self) -> None:
        for child in self.task_frame.winfo_children():
            child.destroy()
        for index, item in enumerate(self.task_rows):
            row = tk.Frame(self.task_frame, bg=CARD)
            row.pack(fill="x", pady=1)
            ttk.Checkbutton(
                row,
                text=self._display_name(str(item["name"])),
                variable=item["enabled_var"],
                style="Task.TCheckbutton",
                width=30,
            ).pack(side="left")
            minute_var = item["minute_var"]
            if minute_var is None:
                tk.Label(row, text="—", bg=CARD, fg=MUTED, width=7, font=("Microsoft YaHei UI", 9)).pack(side="left")
            else:
                ttk.Spinbox(row, from_=1, to=240, width=5, justify="center", textvariable=minute_var).pack(side="left", padx=5)
            max_count = 1 if str(item["name"]).startswith(("04 ", "05 ", "06 ")) else 99
            ttk.Spinbox(row, from_=1, to=max_count, width=5, justify="center", textvariable=item["count_var"]).pack(side="left", padx=5)
            move = tk.Frame(row, bg=CARD)
            move.pack(side="left", padx=(5, 0))
            tk.Button(
                move,
                text="▲",
                bg="#EEF3FA",
                fg=MUTED,
                activebackground="#DFE8F5",
                bd=0,
                width=2,
                cursor="hand2",
                state="disabled" if index == 0 else "normal",
                command=lambda i=index: self._move_task(i, -1),
            ).pack(side="left")
            tk.Button(
                move,
                text="▼",
                bg="#EEF3FA",
                fg=MUTED,
                activebackground="#DFE8F5",
                bd=0,
                width=2,
                cursor="hand2",
                state="disabled" if index == len(self.task_rows) - 1 else "normal",
                command=lambda i=index: self._move_task(i, 1),
            ).pack(side="left", padx=(3, 0))

    def _move_task(self, index: int, direction: int) -> None:
        if self.is_running:
            return
        target = index + direction
        if target < 0 or target >= len(self.task_rows):
            return
        self.task_rows[index], self.task_rows[target] = self.task_rows[target], self.task_rows[index]
        self._render_task_rows()
        self._save_gui_settings()

    def _selected_plan(self) -> list[dict[str, object]]:
        plan: list[dict[str, object]] = []
        for item in self.task_rows:
            if not item["enabled_var"].get():
                continue
            count = int(item["count_var"].get())
            max_count = 1 if str(item["name"]).startswith(("04 ", "05 ", "06 ")) else 99
            if count < 1 or count > max_count:
                raise ValueError(f"{item['name']} 的运行次数必须在 1–{max_count} 之间")
            minute_var = item["minute_var"]
            minutes = int(minute_var.get()) if minute_var is not None else None
            if minutes is not None and not 1 <= minutes <= 240:
                raise ValueError(f"{item['name']} 的运行时间必须在 1–240 分钟之间")
            plan.append({"name": str(item["name"]), "count": count, "minutes": minutes})
        return plan

    def _expanded_tasks(self, plan: list[dict[str, object]]) -> list[str]:
        tasks: list[str] = []
        for item in plan:
            # Reading is executed directly through ADB because QQ Reader blocks
            # Android screenshots on the book page.  MaaFramework cannot move
            # between pipeline nodes there without requesting another frame.
            if str(item["name"]).startswith("01 "):
                continue
            tasks.extend([str(item["name"])] * int(item["count"]))
        return tasks

    def _entry_for_task(self, task_name: str) -> str:
        try:
            interface = json.loads(INTERFACE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"无法读取 interface.json：{exc}") from exc
        for task in interface.get("task", []):
            if task.get("name") == task_name:
                return str(task.get("entry") or task_name)
        return task_name

    def _run_maa_entry(self, entry: str, label: str) -> tuple[int, str]:
        """Run one Maa entry and return its fresh framework log."""
        if not RUNNER_PY.exists() or not RUNNER_SCRIPT.exists():
            raise RuntimeError(
                f"缺少直接 Maa 运行器：{RUNNER_PY} 或 {RUNNER_SCRIPT}")
        log_offset = MAA_LOG_PATH.stat().st_size if MAA_LOG_PATH.exists() else 0
        self.messages.put(("log", f"Maa 执行：{label}（{entry}）"))
        self.process = subprocess.Popen(
            [str(RUNNER_PY), str(RUNNER_SCRIPT), entry,
             "--adb", str(ADB_PATH), "--device", refresh_adb_address()],
            cwd=str(ROOT_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            env=adb_environment(),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        heartbeat_stop = threading.Event()
        heartbeat_thread: threading.Thread | None = None
        dwell_label = LONG_DWELL_ENTRIES.get(entry)
        if dwell_label:
            def write_dwell_heartbeats() -> None:
                minute = 0
                while not heartbeat_stop.wait(60):
                    minute += 1
                    message = f"{dwell_label}仍在正常计时，第 {minute} 分钟"
                    self.messages.put(("log", message))
                    try:
                        append_gui_status(
                            f"GUI {entry}.Heartbeat minute={minute} mode=dwell")
                    except OSError:
                        # The Maa process can rotate its debug log while the
                        # GUI remains healthy; the next minute will retry.
                        pass

            heartbeat_thread = threading.Thread(
                target=write_dwell_heartbeats, name=f"{entry}-heartbeat",
                daemon=True)
            heartbeat_thread.start()
        try:
            for line in self.process.stdout:
                if line.strip():
                    self.messages.put(("log", line.rstrip()))
            code = self.process.wait()
        finally:
            heartbeat_stop.set()
            if heartbeat_thread is not None:
                heartbeat_thread.join(timeout=2)
            self.process = None
        fresh_log = ""
        if MAA_LOG_PATH.exists():
            with MAA_LOG_PATH.open("rb") as maa_log:
                maa_log.seek(log_offset)
                fresh_log = maa_log.read().decode("utf-8", errors="replace")
        return code, fresh_log

    @staticmethod
    def _parse_plan_scan_pages(fresh_log: str) -> dict[str, list[dict[str, object]]]:
        """Extract full-page OCR results emitted by the planning scan."""
        pages: dict[str, list[dict[str, object]]] = {}
        page_names = [f"PlanScanPage{index}" for index in range(5)]
        for line in fresh_log.splitlines():
            # MaaFramework writes OCR records as
            # ``...::analyze] PlanScanPage0 [cache_=...]``.  The former
            # matcher accidentally expected a closing bracket *before* the
            # node name, so every successful scan was parsed as 0/5 pages and
            # the planner always fell back to the full task list.
            page_name = next(
                (name for name in page_names if f" {name} [" in line), None)
            if page_name is None or "[all_results_=" not in line:
                continue
            start = line.find("[all_results_=") + len("[all_results_=")
            end = line.find("] [filtered_results_=", start)
            if end < 0:
                continue
            try:
                results = json.loads(line[start:end])
            except json.JSONDecodeError:
                continue
            if isinstance(results, list) and len(results) >= len(pages.get(page_name, [])):
                pages[page_name] = [item for item in results if isinstance(item, dict)]
        return pages

    @staticmethod
    def _reward_task_statuses(
            pages: dict[str, list[dict[str, object]]]) -> dict[str, bool | None]:
        """Infer completed daily categories from OCR text and row-local buttons.

        ``True`` is a positive completion signal. ``False`` means the category
        was found but still has a go/do action. ``None`` is deliberately
        conservative: the task remains scheduled when the scan is ambiguous.
        """
        # “立即领取” means that the prerequisite is complete but its reward
        # still has to be collected; treating it as completion made the planner
        # skip both the game and ad flows prematurely.  “已获得” is commonly a
        # weekly lottery line and is likewise not proof for a daily category.
        complete_pattern = re.compile(r"已领取|已完成|今日已完成|明日再来")
        incomplete_pattern = re.compile(
            r"立即领取|去阅读|去听书|去玩游戏|去完成|去浏览|去看看|"
            r"再读|再听|今日未听|立即观看|去观看|0\s*/\s*12")

        def text_and_y(item: dict[str, object]) -> tuple[str, float]:
            text = str(item.get("text", "")).replace(" ", "")
            box = item.get("box", [0, 0, 0, 0])
            try:
                y = float(box[1]) + float(box[3]) / 2
            except (TypeError, ValueError, IndexError):
                y = -10000.0
            return text, y

        def category(pattern: str) -> bool | None:
            label_re = re.compile(pattern)
            found = False
            incomplete = False
            for entries in pages.values():
                normalized = [text_and_y(item) for item in entries]
                for label, label_y in normalized:
                    if not label_re.search(label):
                        continue
                    found = True
                    nearby = [text for text, y in normalized
                              if abs(y - label_y) <= 105]
                    row_text = "|".join([label, *nearby])
                    if incomplete_pattern.search(row_text):
                        incomplete = True
                        continue
                    if complete_pattern.search(row_text):
                        return True
            if incomplete:
                return False
            return None if not found else False

        ad_complete: bool | None = None
        for entries in pages.values():
            normalized = [text_and_y(item) for item in entries]
            for label, label_y in normalized:
                if not re.search(r"看小视频|看视频|广告", label):
                    continue
                nearby = "|".join(text for text, y in normalized
                                  if abs(y - label_y) <= 105)
                if re.search(r"0\s*/\s*12|立即观看|去观看", nearby):
                    ad_complete = False
                elif re.search(r"12\s*/\s*12|已领取|已完成|明日再来", nearby):
                    ad_complete = True
        dianping = category(r"大众点评")
        baidu = category(r"百度地图")
        external = True if dianping is True and baidu is True else (
            False if dianping is False or baidu is False else None)
        return {
            "01 ": category(r"每日阅读|阅读.*分钟|今日已读"),
            "02 ": category(r"每日听书|听书.*分钟|今日已听"),
            "03 ": category(r"每日在线游戏|玩游戏领赠币|今日已玩"),
            "04 ": ad_complete,
            "05 ": external,
        }

    def _scan_reward_page_plan(
            self, plan: list[dict[str, object]]) -> list[dict[str, object]]:
        """Scan the reward page first and remove positively completed tasks."""
        self._dismiss_known_qq_popups()
        code, fresh_log = self._run_maa_entry(
            PLAN_SCAN_ENTRY, "00 奖励页多屏检查与动态规划")
        pages = self._parse_plan_scan_pages(fresh_log)
        scan_complete = "QQ_PLAN_SCAN_DONE" in fresh_log and len(pages) >= 3
        if code != 0 or not scan_complete:
            self.messages.put((
                "log",
                f"奖励页扫描未完整结束（退出码 {code}，有效页面 {len(pages)}/5）；"
                "为避免漏做，保留原始任务清单。",
            ))
            return plan

        statuses = self._reward_task_statuses(pages)
        active: list[dict[str, object]] = []
        deferred_claims: list[dict[str, object]] = []
        for item in plan:
            name = str(item["name"])
            if name == LAUNCH_QQ_TASK:
                self.messages.put(("log", "奖励页扫描已负责启动 QQ 阅读，跳过重复启动步骤。"))
                continue
            if name.startswith("07 "):
                deferred_claims.append(item)
                continue
            prefix = name[:3]
            state = statuses.get(prefix)
            if state is True:
                self.messages.put(("log", f"奖励页确认已完成，跳过：{self._display_name(name)}"))
                continue
            self.messages.put((
                "log",
                ("奖励页确认尚未完成，安排执行：" if state is False
                 else "奖励页状态不明确，为避免漏做仍安排执行：")
                + self._display_name(name),
            ))
            active.append(item)
        active.extend(deferred_claims)
        self.messages.put((
            "log",
            "动态任务清单：" + (" → ".join(
                self._display_name(str(item["name"])) for item in active)
                if active else "所有选定任务均已完成"),
        ))
        return active

    def _claim_completed_rewards(self, finished_task: str) -> None:
        """Return to rewards after one category and collect every enabled reward."""
        self._return_to_capturable_page(max_backs=10)
        self._dismiss_known_qq_popups()
        entry = (CLAIM_GAME_REWARD_ENTRY
                 if finished_task.startswith("03 ")
                 else CLAIM_REWARDS_ENTRY)
        code, fresh_log = self._run_maa_entry(
            entry, f"{finished_task}完成后返回奖励页领取")
        if code != 0 or "Tasker.Task.Succeeded" not in fresh_log:
            raise RuntimeError(
                f"{finished_task}完成后奖励领取失败（退出码 {code}）")
        self.messages.put(("log", f"{finished_task}完成后的可领奖励已处理。"))

    def _capture_final_reward_evidence(self) -> Path:
        """Place the reward page at its token summary and save the final PNG."""
        code, fresh_log = self._run_maa_entry(
            FINAL_REWARD_EVIDENCE_ENTRY, "最终奖励页代币截图定位")
        if (code != 0 or "QQ_FINAL_REWARD_EVIDENCE_READY" not in fresh_log
                or "Tasker.Task.Succeeded" not in fresh_log):
            raise RuntimeError(f"未能定位最终奖励页代币区域（退出码 {code}）")
        refresh_adb_address()
        completed = subprocess.run(
            [str(ADB_PATH), "-s", ADB_ADDRESS, "exec-out", "screencap", "-p"],
            cwd=str(ROOT_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=20, env=adb_environment(),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if (completed.returncode != 0 or len(completed.stdout) <= 100
                or not completed.stdout.startswith(b"\x89PNG")):
            raise RuntimeError("最终奖励页未返回有效 PNG 截图")
        FINAL_REWARD_SCREENSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = FINAL_REWARD_SCREENSHOT_PATH.with_suffix(".tmp.png")
        temporary.write_bytes(completed.stdout)
        os.replace(temporary, FINAL_REWARD_SCREENSHOT_PATH)
        token = re.search(r"今日已获赠币\s*(\d+)", fresh_log)
        token_text = f"，今日已获赠币 {token.group(1)}" if token else ""
        self.messages.put((
            "log",
            f"最终奖励页截图已保存：{FINAL_REWARD_SCREENSHOT_PATH}{token_text}",
        ))
        return FINAL_REWARD_SCREENSHOT_PATH

    def _adb(self, *args: str, timeout: int = 20) -> None:
        refresh_adb_address()
        result = subprocess.run(
            [str(ADB_PATH), "-s", ADB_ADDRESS, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            env=adb_environment(),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            output = result.stdout.decode("gb18030", errors="replace").strip()
            raise RuntimeError(output or f"ADB 退出代码 {result.returncode}")

    def _adb_reader_focus(self) -> str:
        """Return the currently focused QQ Reader activity/window."""
        refresh_adb_address()
        try:
            result = subprocess.run(
                [str(ADB_PATH), "-s", ADB_ADDRESS, "shell", "dumpsys",
                 "window"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                timeout=12, env=adb_environment(),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        return result.stdout.decode("utf-8", errors="replace")

    def _wait_reader_page(self, timeout: float = 8.0) -> bool:
        """Wait until QQ Reader reports its protected ReaderPageActivity."""
        deadline = time.monotonic() + max(0.5, timeout)
        while time.monotonic() < deadline:
            focus = self._adb_reader_focus()
            if "ReaderPageActivity" in focus:
                return True
            if self.stop_requested.wait(0.25):
                raise InterruptedError("用户停止任务")
        return False

    def _adb_ui_contains(self, expected: str) -> bool:
        """Check a visible, capturable QQ Reader page through UI Automator."""
        refresh_adb_address()
        remote = "/sdcard/gameflow_qq_window.xml"
        common = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "timeout": 12,
            "env": adb_environment(),
            "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
        }
        try:
            dumped = subprocess.run(
                [str(ADB_PATH), "-s", ADB_ADDRESS, "shell", "uiautomator",
                 "dump", remote], **common)
            if dumped.returncode != 0:
                return False
            fetched = subprocess.run(
                [str(ADB_PATH), "-s", ADB_ADDRESS, "shell", "cat", remote],
                **common)
            return (fetched.returncode == 0
                    and expected in fetched.stdout.decode("utf-8", errors="replace"))
        except (OSError, subprocess.SubprocessError):
            return False

    def _adb_screenshot_available(self) -> bool:
        """Return whether Android currently permits Maa/ADB to capture a frame."""
        refresh_adb_address()
        try:
            result = subprocess.run(
                [str(ADB_PATH), "-s", ADB_ADDRESS, "exec-out", "screencap", "-p"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=15,
                env=adb_environment(),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.SubprocessError):
            return False
        data = result.stdout
        return result.returncode == 0 and len(data) > 100 and data.startswith(b"\x89PNG")

    def _dismiss_known_qq_popups(self, max_passes: int = 3) -> bool:
        """Dismiss only known, safe QQ Reader dialogs through UI Automator.

        The handler is deliberately text-gated.  It never chooses an install
        action and never clicks a generic coordinate: update prompts are
        cancelled, exit prompts are cancelled, and network failures use their
        explicit retry action.
        """
        refresh_adb_address()
        remote = "/sdcard/gameflow_qq_window.xml"
        common = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "timeout": 12,
            "env": adb_environment(),
            "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
        }
        clicked_any = False
        for _ in range(max(1, max_passes)):
            try:
                dumped = subprocess.run(
                    [str(ADB_PATH), "-s", ADB_ADDRESS, "shell", "uiautomator",
                     "dump", remote], **common)
                if dumped.returncode != 0:
                    break
                fetched = subprocess.run(
                    [str(ADB_PATH), "-s", ADB_ADDRESS, "shell", "cat", remote],
                    **common)
                if fetched.returncode != 0:
                    break
                root = ET.fromstring(
                    fetched.stdout.decode("utf-8", errors="replace"))
            except (OSError, subprocess.SubprocessError, ET.ParseError):
                break

            all_text = " ".join(
                f"{node.attrib.get('text', '')} "
                f"{node.attrib.get('content-desc', '')}"
                for node in root.iter())
            action_labels: tuple[str, ...] = ()
            reason = ""
            if any(marker in all_text for marker in (
                    "已下载新版本", "是否安装", "安装新版本", "立即安装")):
                action_labels = ("取消", "暂不安装", "稍后再说", "以后再说")
                reason = "新版本安装提示"
            elif any(marker in all_text for marker in (
                    "退出QQ阅读", "退出 QQ 阅读", "退出软件",
                    "确定退出", "是否退出")):
                action_labels = ("取消", "暂不退出", "继续使用")
                reason = "退出确认"
            elif any(marker in all_text for marker in (
                    "网络异常", "网络错误", "加载失败", "连接失败",
                    "请检查网络", "网络不给力")):
                action_labels = ("重试", "重新加载", "刷新", "确定")
                reason = "网络重试"
            elif any(marker in all_text for marker in (
                    "温馨提示", "操作提示", "阅读提示")):
                action_labels = ("我知道了", "知道了", "取消", "确定")
                reason = "常规提示"
            if not action_labels:
                break

            target = None
            for expected in action_labels:
                for node in root.iter():
                    label = (node.attrib.get("text", "") or
                             node.attrib.get("content-desc", "")).strip()
                    if label != expected:
                        continue
                    match = re.fullmatch(
                        r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]",
                        node.attrib.get("bounds", ""))
                    if match:
                        target = (expected, tuple(map(int, match.groups())))
                        break
                if target is not None:
                    break
            if target is None:
                self.messages.put((
                    "log", f"检测到 QQ 阅读{reason}，但未找到安全操作按钮。"))
                break
            label, (left, top, right, bottom) = target
            self._adb("shell", "input", "tap",
                      str((left + right) // 2), str((top + bottom) // 2))
            clicked_any = True
            self.messages.put((
                "log", f"检测到 QQ 阅读{reason}，已点击“{label}”。"))
            if self.stop_requested.wait(0.8):
                raise InterruptedError("用户停止任务")
        return clicked_any

    def _dismiss_qq_exit_dialog(self) -> bool:
        """Compatibility wrapper for callers that expect exit handling."""
        return self._dismiss_known_qq_popups(max_passes=1)

    def _return_to_capturable_page(self, max_backs: int = 6) -> None:
        """Leave QQ Reader's FLAG_SECURE book page before starting Maa."""
        if self._adb_screenshot_available():
            return
        for attempt in range(1, max_backs + 1):
            self._adb("shell", "input", "keyevent", "4")
            if self.stop_requested.wait(1.5):
                raise InterruptedError("用户停止任务")
            if self._dismiss_qq_exit_dialog():
                if self.stop_requested.wait(1):
                    raise InterruptedError("用户停止任务")
                continue
            if self._adb_screenshot_available():
                self.messages.put(("log", f"已返回可截图页面（返回 {attempt} 次），Maa 可以继续识别。"))
                return
        raise RuntimeError("多次返回后 QQ 阅读页面仍禁止截图，无法交给 Maa 继续执行")

    def _return_to_shelf(self, max_backs: int = 4,
                         allow_recovery: bool = True) -> None:
        """Ensure Maa sees the actual bookshelf, not a capturable reward page."""
        self._return_to_capturable_page(max_backs=max_backs + 2)
        self._dismiss_known_qq_popups()
        for attempt in range(0, max_backs + 1):
            if self._adb_ui_contains("书架"):
                if attempt:
                    self.messages.put(("log", f"已返回书架（额外返回 {attempt} 次）。"))
                return
            if attempt >= max_backs:
                break
            self._adb("shell", "input", "keyevent", "4")
            if self.stop_requested.wait(1.2):
                raise InterruptedError("用户停止任务")
            self._dismiss_qq_exit_dialog()
        if allow_recovery:
            self.messages.put((
                "log",
                "未能返回书架；重新启动 QQ 阅读、处理弹窗并扫描奖励页后再试一次。",
            ))
            self._adb("shell", "monkey", "-p", "com.qq.reader", "-c",
                      "android.intent.category.LAUNCHER", "1")
            if self.stop_requested.wait(2):
                raise InterruptedError("用户停止任务")
            self._dismiss_known_qq_popups()
            self._run_maa_entry(
                PLAN_SCAN_ENTRY, "返回书架失败后的奖励页恢复扫描")
            self._return_to_shelf(max_backs=max_backs + 2,
                                  allow_recovery=False)
            return
        raise RuntimeError("页面恢复和奖励页重扫后仍未能返回 QQ 阅读书架")

    def _run_direct_reading(self, plan: list[dict[str, object]]) -> None:
        readings = [item for item in plan if str(item["name"]).startswith("01 ")]
        if readings:
            append_gui_status(
                "GUI Tasker.Task.Starting entry=DirectDailyReadingFlow")
        total = sum(int(item["count"]) for item in readings)
        current = 0
        for item in readings:
            for _ in range(int(item["count"])):
                current += 1
                minutes = int(item["minutes"])
                segment_count = max(
                    1, (minutes + DIRECT_READING_DWELL_SEGMENT_MINUTES - 1)
                    // DIRECT_READING_DWELL_SEGMENT_MINUTES)
                remaining_minutes = minutes
                for segment in range(1, segment_count + 1):
                    dwell_minutes = min(
                        DIRECT_READING_DWELL_SEGMENT_MINUTES, remaining_minutes)
                    self.messages.put((
                        "log",
                        f"阅读第 {current}/{total} 次，第 {segment}/{segment_count} 段："
                        "由 Maa 识别目标书，进入正文后保底停留。",
                    ))
                    self._adb("shell", "monkey", "-p", "com.qq.reader", "-c",
                              "android.intent.category.LAUNCHER", "1")
                    if self.stop_requested.wait(3):
                        raise InterruptedError("用户停止任务")
                    self._return_to_shelf()
                    selector_succeeded = False
                    selector_error = ""
                    # The terminal selector stops as soon as it clicks the
                    # book.  Maa must never request another screenshot after
                    # ReaderPageActivity becomes FLAG_SECURE.
                    try:
                        for selector_attempt in range(1, 6):
                            if selector_attempt > 1:
                                self.messages.put((
                                    "log",
                                    f"Maa 选书未获得有效截图，第 {selector_attempt} 次返回书架重试。",
                                ))
                                self._adb("shell", "input", "keyevent", "4")
                                if self.stop_requested.wait(2):
                                    raise InterruptedError("用户停止任务")
                            log_offset = MAA_LOG_PATH.stat().st_size if MAA_LOG_PATH.exists() else 0
                            self.process = subprocess.Popen(
                                [str(RUNNER_PY), str(RUNNER_SCRIPT), "DirectReadingFlow",
                                 "--adb", str(ADB_PATH),
                                 "--device", refresh_adb_address()],
                                cwd=str(ROOT_DIR),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace",
                                env=adb_environment(),
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                            )
                            for line in self.process.stdout:
                                if line.strip():
                                    self.messages.put(("log", line.rstrip()))
                            selector_code = self.process.wait()
                            self.process = None
                            fresh_log = ""
                            if MAA_LOG_PATH.exists():
                                with MAA_LOG_PATH.open("rb") as maa_log:
                                    maa_log.seek(log_offset)
                                    fresh_log = maa_log.read().decode("utf-8", errors="replace")
                            matched = (
                                ("TemplateMatcher::analyze] ReadingFindBook" in fresh_log
                                 or '"name":"ReadingFindBookByTitleTerminal"' in fresh_log)
                                and '"success":true' in fresh_log
                                and "Tasker.Task.Succeeded" in fresh_log
                            )
                            if selector_code == 0 and matched:
                                selector_succeeded = True
                                break
                            selector_error = (
                                f"runner={selector_code}; "
                                + ("Maa 未产出模板匹配/点击成功记录" if not matched else "未知错误")
                            )
                        if not selector_succeeded:
                            self.messages.put((
                                "log",
                                f"Maa 目标书模板识别失败（{selector_error}），"
                                "改为逐个点击书架可见书目并回读正文 Activity。",
                            ))
                            for fallback_x, fallback_y in (
                                    (250, 470), (250, 610), (250, 760)):
                                self._adb("shell", "input", "tap",
                                          str(fallback_x), str(fallback_y))
                                if self._wait_reader_page(6):
                                    selector_succeeded = True
                                    self.messages.put((
                                        "log",
                                        f"书架保底点击 ({fallback_x}, {fallback_y}) "
                                        "已确认进入正文页。",
                                    ))
                                    break
                                self._adb("shell", "input", "keyevent", "4")
                                if self.stop_requested.wait(1.5):
                                    raise InterruptedError("用户停止任务")
                            if not selector_succeeded:
                                raise RuntimeError(
                                    f"Maa 与书架保底点击均未能进入正文页：{selector_error}")
                    finally:
                        self.process = None
                    if not self._wait_reader_page(8):
                        self._adb("shell", "input", "tap", "500", "1126")
                        self.messages.put(("log", "未直接进入正文页，已按页面状态点击“查看原文”备用入口。"))
                        if not self._wait_reader_page(8):
                            raise RuntimeError("点击目标书后未进入 QQ 阅读正文页")

                    # Auto-reading remains a best-effort enhancement.  Its
                    # visual state cannot be read back on a secure page, so a
                    # successful ReaderPageActivity dwell is the completion
                    # criterion even when one of these taps fails.
                    try:
                        self._adb("shell", "input", "tap", "360", "640")
                        if self.stop_requested.wait(1):
                            raise InterruptedError("用户停止任务")
                        self._adb("shell", "input", "tap", "450", "1214")
                        if self.stop_requested.wait(1):
                            raise InterruptedError("用户停止任务")
                        self._adb("shell", "input", "tap", "360", "1125")
                        self.messages.put(("log", "已尝试点击“自动阅读”；本段仍以正文停留计时为准。"))
                    except RuntimeError as exc:
                        self.messages.put(("log", f"自动阅读按钮操作未确认，继续使用正文停留保底：{exc}"))

                    for elapsed_minute in range(1, dwell_minutes + 1):
                        if self.stop_requested.wait(60):
                            raise InterruptedError("用户停止任务")
                        heartbeat = (
                            f"正文停留第 {current}/{total} 次，第 {segment}/{segment_count} 段："
                            f"{elapsed_minute}/{dwell_minutes} 分钟")
                        self.messages.put(("log", heartbeat))
                        append_gui_status(
                            f"GUI DirectDailyReadingFlow.Heartbeat "
                            f"round={current}/{total} segment={segment}/{segment_count} "
                            f"minute={elapsed_minute}/{dwell_minutes} mode=dwell")
                    self._return_to_capturable_page()
                    remaining_minutes -= dwell_minutes
                    self.messages.put((
                        "log",
                        f"阅读第 {current}/{total} 次，第 {segment}/{segment_count} 段完成；已返回书架。",
                    ))

    def _save_gui_settings(self) -> None:
        tasks = []
        for item in self.task_rows:
            try:
                count = int(item["count_var"].get())
            except (tk.TclError, ValueError):
                count = self._default_count(str(item["name"]))
            minute_var = item["minute_var"]
            try:
                minutes = int(minute_var.get()) if minute_var is not None else None
            except (tk.TclError, ValueError):
                minutes = self._default_minutes(str(item["name"])) if minute_var is not None else None
            tasks.append(
                {
                    "name": str(item["name"]),
                    "enabled": bool(item["enabled_var"].get()),
                    "minutes": minutes,
                    "count": count,
                }
            )
        temp_path = GUI_SETTINGS_PATH.with_suffix(".tmp")
        temp_path.write_text(json.dumps(
            {"tasks": tasks,
             "dynamic_planning": bool(self.dynamic_planning_var.get())},
            ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
        os.replace(temp_path, GUI_SETTINGS_PATH)

    def _update_selection_summary(self) -> None:
        selected = 0
        executions = 0
        for item in self.task_rows:
            if item["enabled_var"].get():
                selected += 1
                try:
                    executions += max(0, int(item["count_var"].get()))
                except (tk.TclError, ValueError):
                    pass
        self.summary_label.configure(
            text=f"已选择 {selected} 项，共执行 {executions} 次" if selected else "请选择至少一个任务"
        )

    def _append_log(self, message: str) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{now}] {message.rstrip()}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_running(self, running: bool) -> None:
        self.is_running = running
        self.start_button.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")
        self.qq_button.configure(state="disabled" if running else "normal")
        self.cli_button.configure(state="disabled" if running else "normal")
        if running:
            self._set_widget_tree_state(self.task_frame, "disabled")
        else:
            self._render_task_rows()
        if running:
            self.run_state_label.configure(text="运行中", bg="#E7F8F1", fg=SUCCESS)
        else:
            self.run_state_label.configure(text="空闲", bg="#EEF2F7", fg=MUTED)

    def _set_widget_tree_state(self, widget: tk.Misc, state: str) -> None:
        for child in widget.winfo_children():
            try:
                child.configure(state=state)
            except tk.TclError:
                pass
            self._set_widget_tree_state(child, state)

    def _check_files(self) -> bool:
        missing = [path for path in (
            RUNNER_PY, RUNNER_SCRIPT, SOLVER_SCRIPT,
            INTERFACE_PATH, CONFIG_PATH, PIPELINE_PATH,
        ) if not path.exists()]
        if not missing:
            return True
        messagebox.showerror("文件缺失", "以下运行文件不存在：\n\n" + "\n".join(str(path) for path in missing))
        return False

    def _check_connection(self) -> None:
        if not ADB_PATH.exists():
            messagebox.showerror("未找到 ADB", str(ADB_PATH))
            return
        self.connection_label.configure(text="正在检查模拟器连接…")
        self.status_dot.configure(fg="#E7A928")

        def worker() -> None:
            try:
                connected = self._adb_connected()
                self.messages.put(("connection", "ok" if connected else "missing"))
            except Exception as exc:
                self.messages.put(("connection_error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _adb_connected(self) -> bool:
        refresh_adb_address()
        completed = subprocess.run(
            [str(ADB_PATH), "devices"],
            capture_output=True,
            text=True,
            encoding=locale.getpreferredencoding(False),
            errors="replace",
            timeout=8,
            env=adb_environment(),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return f"{ADB_ADDRESS}\tdevice" in completed.stdout

    def _ensure_emulator_connected(self, timeout: int = 180) -> None:
        """Launch MuMu 0, reconnect its isolated ADB server, and wait for Android."""
        if not ADB_PATH.exists():
            raise RuntimeError(f"未找到 MuMu ADB：{ADB_PATH}")
        if self._adb_connected() and self._android_boot_completed():
            return

        self.messages.put(("log", "正在自动启动并连接 MuMu 模拟器（实例 0）…"))
        if MUMU_MANAGER_PATH.exists():
            launched = subprocess.run(
                [str(MUMU_MANAGER_PATH), "control", "--vmindex", "0", "launch"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=20,
                env=adb_environment(),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if launched.returncode != 0:
                output = launched.stdout.decode("utf-8", errors="replace").strip()
                raise RuntimeError(f"MuMu 实例 0 启动失败：{output or launched.returncode}")
        elif MUMU_PATH.exists():
            subprocess.Popen([str(MUMU_PATH)], cwd=str(MUMU_PATH.parent))
        else:
            raise RuntimeError("未找到 MuMuManager.exe 或 MuMuPlayer.exe")

        deadline = time.monotonic() + max(30, timeout)
        next_reset_at = 0.0
        last_message = "模拟器尚未开放 ADB 端口"
        while time.monotonic() < deadline:
            if self.stop_requested.is_set():
                raise InterruptedError("用户停止任务")
            now = time.monotonic()
            refresh_adb_address()
            if now >= next_reset_at:
                # Clear a stale offline transport without killing the shared
                # 5038 server used by other MuMu integrations.
                subprocess.run(
                    [str(ADB_PATH), "disconnect", ADB_ADDRESS],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=8,
                    env=adb_environment(),
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                next_reset_at = now + 20
            try:
                connected = subprocess.run(
                    [str(ADB_PATH), "connect", ADB_ADDRESS],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=12,
                    env=adb_environment(),
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                last_message = connected.stdout.decode(
                    locale.getpreferredencoding(False), errors="replace").strip()
                if self._adb_connected() and self._android_boot_completed():
                    self.messages.put(("connection", "ok"))
                    self.messages.put(("log", "MuMu Android 已启动，ADB 连接可以交给 Maa。"))
                    return
            except (OSError, subprocess.SubprocessError) as exc:
                last_message = str(exc)
            if self.stop_requested.wait(2):
                raise InterruptedError("用户停止任务")
        raise RuntimeError(
            f"等待 MuMu/ADB {timeout} 秒后仍未就绪（{ADB_ADDRESS}）：{last_message}")

    def _android_boot_completed(self) -> bool:
        refresh_adb_address()
        try:
            completed = subprocess.run(
                [str(ADB_PATH), "-s", ADB_ADDRESS, "shell", "getprop", "sys.boot_completed"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=8,
                env=adb_environment(),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return completed.returncode == 0 and completed.stdout.strip() == b"1"

    def _start_emulator(self) -> None:
        self.status_dot.configure(fg="#E7A928")
        self.connection_label.configure(text="正在启动 MuMu 模拟器…")
        self._append_log("正在启动实例 0，并自动修复 ADB 连接。")

        def worker() -> None:
            try:
                self._ensure_emulator_connected()
                self._dismiss_known_qq_popups()
            except Exception as exc:
                self.messages.put(("connection_error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _start_qq_reader(self) -> None:
        if self.is_running or not self._check_files():
            return
        plan = [{"name": LAUNCH_QQ_TASK, "count": 1, "minutes": None}]
        self._run_plan(plan, "将先自动连接模拟器，再启动 QQ 阅读并处理已知开屏弹窗。")

    def _write_run_config(self, plan: list[dict[str, object]]) -> None:
        refresh_adb_address()
        self.original_config = CONFIG_PATH.read_bytes()
        self.original_pipeline = PIPELINE_PATH.read_bytes()
        config = json.loads(self.original_config.decode("utf-8"))
        adb_config = config.get("adb")
        if isinstance(adb_config, dict):
            # MaaPiCli passes this field verbatim to the native controller.
            # An omitted/legacy string value is converted to an empty string
            # and MaaAdbControlUnit rejects it before the first screenshot.
            # Keep a real MuMu extra-config object so both the explicit ADB
            # path and the emulator-specific input/screencap backends remain
            # available when the GUI is launched from GameFlow.
            adb_config["adb_path"] = str(ADB_PATH).replace("\\", "/")
            adb_config["address"] = ADB_ADDRESS
            adb_config["name"] = ADB_DEVICE_NAME
            adb_config["config"] = {
                "extras": {
                    "mumu": {
                        "enable": True,
                        "index": 0,
                        "path": "D:/Program Files/Netease/MuMu Player 12",
                    }
                }
            }
        tasks = self._expanded_tasks(plan)
        config["task"] = [{"name": name, "option": []} for name in tasks]
        temp_path = CONFIG_PATH.with_suffix(".gui.tmp")
        temp_path.write_text(json.dumps(config, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
        os.replace(temp_path, CONFIG_PATH)

        pipeline = json.loads(self.original_pipeline.decode("utf-8"))
        for item in plan:
            node = self._timing_node(str(item["name"]))
            if node and item["minutes"] is not None:
                pipeline[node]["post_delay"] = int(item["minutes"]) * 60_000
        pipeline_temp = PIPELINE_PATH.with_suffix(".gui.tmp")
        pipeline_temp.write_text(json.dumps(pipeline, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
        os.replace(pipeline_temp, PIPELINE_PATH)

    def _restore_config(self) -> None:
        if self.original_config is not None:
            temp_path = CONFIG_PATH.with_suffix(".restore.tmp")
            temp_path.write_bytes(self.original_config)
            os.replace(temp_path, CONFIG_PATH)
            self.original_config = None
        if self.original_pipeline is not None:
            pipeline_temp = PIPELINE_PATH.with_suffix(".restore.tmp")
            pipeline_temp.write_bytes(self.original_pipeline)
            os.replace(pipeline_temp, PIPELINE_PATH)
            self.original_pipeline = None

    def _start(self) -> None:
        if self.is_running or not self._check_files():
            return
        try:
            plan = self._selected_plan()
        except (tk.TclError, ValueError) as exc:
            messagebox.showwarning("参数不正确", str(exc))
            return
        if not plan:
            messagebox.showwarning("未选择任务", "请至少选择一个需要执行的任务。")
            return
        self._save_gui_settings()
        self._run_plan(plan)

    def _run_plan(self, plan: list[dict[str, object]], intro: str | None = None) -> None:
        try:
            self._write_run_config(plan)
        except Exception as exc:
            try:
                self._restore_config()
            except Exception:
                pass
            messagebox.showerror("配置失败", f"无法准备运行配置：\n{exc}")
            return

        tasks = self._expanded_tasks(plan)
        descriptions = []
        for item in plan:
            duration = f"，每次 {item['minutes']} 分钟" if item["minutes"] is not None else ""
            descriptions.append(f"{self._display_name(str(item['name']))}（重复 {item['count']} 次{duration}）")
        self._append_log("准备执行：" + " → ".join(descriptions))
        self._append_log(intro or "所有任务均为串行执行；听书结束后会先暂停，再进入后续任务。")
        self._set_running(True)

        def worker() -> None:
            code = -1
            watch_stop = threading.Event()
            self.run_failed = False
            self.captcha_notified = False
            self.captcha_solver_running = False
            self.ad_locator_running = False
            self.ad_locator_last_at = 0.0
            self.ad_locator_attempts = 0
            self.slide_solver_running = False
            self.slide_solver_last_at = 0.0
            self.slide_solver_attempts = 0
            self.stop_requested.clear()
            log_offset = MAA_LOG_PATH.stat().st_size if MAA_LOG_PATH.exists() else 0
            watch_thread = threading.Thread(
                target=self._watch_maa_log,
                args=(log_offset, watch_stop),
                daemon=True,
            )
            watch_thread.start()
            try:
                self._ensure_emulator_connected()
                # QQ Reader may resume directly inside a FLAG_SECURE正文页.
                # Maa cannot capture that frame, so leave it before the
                # reward-page-first planning scan.
                self._return_to_capturable_page(max_backs=10)
                if self.dynamic_planning_var.get():
                    active_plan = self._scan_reward_page_plan(plan)
                else:
                    active_plan = plan
                pending: list[dict[str, object]] = []
                for item in active_plan:
                    if (str(item["name"]) == LAUNCH_QQ_TASK
                            or str(item["name"]).startswith("07 ")):
                        continue
                    # Split repeated work into independently verifiable units.
                    # After every unit the reward page is claimed and rescanned;
                    # duplicate units disappear as soon as the category is done.
                    for _ in range(int(item["count"])):
                        pending.append({**item, "count": 1})
                code = 0
                while pending:
                    if self.stop_requested.is_set():
                        raise InterruptedError("用户停止任务")
                    item = pending.pop(0)
                    task_name = str(item["name"])
                    self._dismiss_known_qq_popups()
                    if task_name.startswith("01 "):
                        self._run_direct_reading([item])
                    elif task_name.startswith("03 "):
                        # The reward page can expose a ready-to-claim game
                        # bonus even while the planner still marks the game
                        # category incomplete.  Claim that state first: it
                        # avoids needlessly opening a third-party game's
                        # first-run agreement screen.  A non-zero result
                        # means no eligible reward was found, so the normal
                        # timed game flow remains the fallback.
                        claim_code, _ = self._run_maa_entry(
                            CLAIM_GAME_REWARD_ENTRY, "每日游戏奖励预检")
                        if claim_code == 0:
                            self.messages.put((
                                "log",
                                "每日游戏奖励已领取或已完成，跳过第三方游戏计时。",
                            ))
                            continue
                        entry = self._entry_for_task(task_name)
                        task_code, _ = self._run_maa_entry(entry, task_name)
                        if task_code != 0:
                            code = task_code
                            raise RuntimeError(
                                f"Maa 任务失败：{task_name}（退出码 {task_code}）")
                    else:
                        entry = self._entry_for_task(task_name)
                        task_code, _ = self._run_maa_entry(entry, task_name)
                        if task_code != 0:
                            code = task_code
                            raise RuntimeError(
                                f"Maa 任务失败：{task_name}（退出码 {task_code}）")

                    display_name = self._display_name(task_name)
                    self._claim_completed_rewards(display_name)
                    if pending:
                        if self.dynamic_planning_var.get():
                            self.messages.put((
                                "log",
                                f"{display_name}奖励领取后重新扫描，规划剩余任务。",
                            ))
                            pending = [
                                candidate
                                for candidate in self._scan_reward_page_plan(pending)
                                if not str(candidate["name"]).startswith("07 ")
                            ]
                        else:
                            self.messages.put((
                                "log",
                                f"{display_name}已完成；动态规划已关闭，继续按原清单执行。",
                            ))

                # A final pass collects rewards unlocked by delayed server
                # settlement, then positions the page at today's token total.
                self._claim_completed_rewards("全部计划任务")
                self._capture_final_reward_evidence()
            except Exception as exc:
                code = code if code not in (0, -1) else 1
                self.run_failed = True
                self.messages.put(("log", f"启动失败：{exc}"))
                append_gui_status(f"GUI FullDailyFlow.Failed error={exc!s}")
            finally:
                watch_stop.set()
                watch_thread.join(timeout=1)
                if self.run_failed and code == 0:
                    code = 2
                if code == 0:
                    append_gui_status("GUI FullDailyFlow.Completed")
                try:
                    self._restore_config()
                except Exception as exc:
                    self.messages.put(("log", f"恢复 CLI 配置失败：{exc}"))
                self.process = None
                self.messages.put(("finished", str(code)))

        threading.Thread(target=worker, daemon=True).start()

    def _watch_maa_log(self, offset: int, stop: threading.Event) -> None:
        pending = ""
        while not stop.wait(0.5):
            try:
                if not MAA_LOG_PATH.exists():
                    continue
                with MAA_LOG_PATH.open("rb") as stream:
                    stream.seek(offset)
                    chunk = stream.read()
                    offset = stream.tell()
                if not chunk:
                    continue
                pending += chunk.decode("utf-8", errors="replace")
                lines = pending.splitlines(keepends=True)
                if lines and not lines[-1].endswith(("\n", "\r")):
                    pending = lines.pop()
                else:
                    pending = ""
                for line in lines:
                    if (
                        "Node.Recognition.Succeeded" in line
                        and '"name":"AdReturnStable"' in line
                    ):
                        self.captcha_notified = False
                        self.captcha_solver_running = False
                    transient_selector_failure = (
                        "Tasker.Task.Failed" in line
                        and '"entry":"DirectReadingFlow"' in line
                    )
                    if transient_selector_failure:
                        self.messages.put((
                            "log",
                            "目标书首次识别未命中，GUI 将返回书架后自动重试，不计为整轮失败。",
                        ))
                    elif any(
                        marker in line
                        for marker in (
                            "Tasker.Task.Failed",
                            "Failed to connect controller",
                            "No available screencap method",
                            "failed to init screencap",
                        )
                    ):
                        self.run_failed = True
                    if (
                        not self.captcha_solver_running
                        and not self.captcha_notified
                        and "Node.Recognition.Succeeded" in line
                        and '"name":"AdCaptchaDetected"' in line
                    ):
                        self.captcha_notified = True
                        self.captcha_solver_running = True
                        self.messages.put(
                            (
                                "log",
                                "检测到图片点选验证码：开始自动按顺序点选并提交。",
                            )
                        )
                        threading.Thread(target=self._solve_captcha, daemon=True).start()
                    if (
                        not self.ad_locator_running
                        and "Node.Recognition.Failed" in line
                        and ('"name":"AdClickWatch"' in line
                             or '"name":"AdVideoCounterVisible"' in line)
                        and time.monotonic() - self.ad_locator_last_at > 8
                        and self.ad_locator_attempts < 8
                    ):
                        self.ad_locator_running = True
                        self.ad_locator_last_at = time.monotonic()
                        self.ad_locator_attempts += 1
                        self.messages.put((
                            "log",
                            "未读到广告入口，开始定位广告卡片并点击观看按钮。",
                        ))
                        threading.Thread(target=self._locate_ad, daemon=True).start()
                    if (
                        not self.slide_solver_running
                        and ("screencap failed" in line
                             or ("Node.Recognition.Failed" in line
                                 and ('"name":"AdClickWatch"' in line
                                      or '"name":"AdVideoCounterVisible"' in line)))
                        and time.monotonic() - self.slide_solver_last_at > 8
                        and self.slide_solver_attempts < 6
                    ):
                        self.slide_solver_running = True
                        self.slide_solver_last_at = time.monotonic()
                        self.slide_solver_attempts += 1
                        self.messages.put((
                            "log",
                            "检测到可能的滑动验证码，开始自动识别并滑动。",
                        ))
                        threading.Thread(target=self._solve_slide_captcha, daemon=True).start()
            except Exception as exc:
                self.messages.put(("log", f"读取 MAA 状态日志失败：{exc}"))
                return

    def _solve_captcha(self) -> None:
        """Automatically solve the ordered-image CAPTCHA and preserve evidence."""
        evidence = DEV_DIR / "debug" / f"captcha_{datetime.now():%Y%m%d_%H%M%S}.png"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        try:
            completed = subprocess.run(
                [str(ADB_PATH), "-s", ADB_ADDRESS, "exec-out", "screencap", "-p"],
                cwd=str(ROOT_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                timeout=20,
                env=adb_environment(),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if (completed.returncode == 0 and len(completed.stdout) > 100
                    and completed.stdout.startswith(b"\x89PNG")):
                evidence.write_bytes(completed.stdout)
                self.messages.put((
                    "log",
                    f"验证码现场已保存：{evidence}。开始自动按顺序点选并提交。",
                ))
            else:
                self.messages.put(("log", "验证码截图失败；仍尝试自动求解。"))
        except Exception as exc:
            self.messages.put(("log", f"保存验证码现场失败：{exc}；仍尝试自动求解。"))

        try:
            if not RUNNER_PY.exists() or not SOLVER_SCRIPT.exists():
                raise RuntimeError("验证码求解器不可用")
            solver = subprocess.run(
                [str(RUNNER_PY), str(SOLVER_SCRIPT),
                 "--adb", str(ADB_PATH), "--device", ADB_ADDRESS,
                 "--submit", "--click-engine", "maa"],
                cwd=str(ROOT_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", timeout=90,
                env=adb_environment(),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            parsed = {}
            for line in reversed(solver.stdout.splitlines()):
                try:
                    parsed = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
            if parsed.get("submitted") and not parsed.get("captcha_still_visible"):
                self.messages.put(("log", "验证码已自动按顺序点选并提交，Maa 将继续执行。"))
            else:
                self.messages.put((
                    "log",
                    f"验证码自动求解未确认成功：{solver.stdout[-400:]}；请人工处理当前页面。",
                ))
        except Exception as exc:
            self.messages.put(("log", f"验证码自动求解异常：{exc}；请人工处理当前页面。"))
        finally:
            self.captcha_solver_running = False

    def _locate_ad(self) -> None:
        """Locate the QQ Reader ad div and click the watch button inside it."""
        try:
            if not RUNNER_PY.exists() or not AD_LOCATOR_SCRIPT.exists():
                raise RuntimeError("广告定位器不可用")
            locator = subprocess.run(
                [str(RUNNER_PY), str(AD_LOCATOR_SCRIPT),
                 "--log", str(MAA_LOG_PATH),
                 "--adb", str(ADB_PATH), "--device", ADB_ADDRESS,
                 "--click", "--click-engine", "maa"],
                cwd=str(ROOT_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", timeout=45,
                env=adb_environment(),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            parsed = {}
            for line in reversed(locator.stdout.splitlines()):
                try:
                    parsed = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
            if parsed.get("found") and parsed.get("clicked"):
                self.messages.put((
                    "log",
                    f"广告卡片已定位并点击观看按钮：{parsed.get('method', '')} @ {parsed.get('point')}",
                ))
            else:
                self.messages.put((
                    "log",
                    f"广告定位未确认：{locator.stdout[-400:]}",
                ))
        except Exception as exc:
            self.messages.put(("log", f"广告定位异常：{exc}"))
        finally:
            self.ad_locator_running = False

    def _solve_slide_captcha(self) -> None:
        """Detect and swipe a slide CAPTCHA through the local MaaFramework controller."""
        try:
            if not RUNNER_PY.exists() or not SLIDE_SOLVER_SCRIPT.exists():
                raise RuntimeError("滑块验证码求解器不可用")
            solver = subprocess.run(
                [str(RUNNER_PY), str(SLIDE_SOLVER_SCRIPT),
                 "--adb", str(ADB_PATH), "--device", ADB_ADDRESS, "--swipe"],
                cwd=str(ROOT_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", timeout=45,
                env=adb_environment(),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            parsed = {}
            for line in reversed(solver.stdout.splitlines()):
                try:
                    parsed = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
            if parsed.get("found") and parsed.get("swiped"):
                self.messages.put((
                    "log",
                    f"滑动验证码已自动完成：距离 {parsed.get('distance')}px",
                ))
            else:
                self.messages.put((
                    "log",
                    f"未检测到滑动验证码或滑动未确认：{solver.stdout[-300:]}",
                ))
        except Exception as exc:
            self.messages.put(("log", f"滑动验证码求解异常：{exc}"))
        finally:
            self.slide_solver_running = False

    def _stop(self) -> None:
        self.stop_requested.set()
        process = self.process
        if process is None or process.poll() is not None:
            return
        self._append_log("正在停止当前任务…")
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            else:
                process.terminate()
        except Exception as exc:
            self._append_log(f"停止失败：{exc}")

    def _open_cli(self) -> None:
        if not self._check_files():
            return
        try:
            subprocess.Popen(
                ["cmd.exe", "/k", f'cd /d "{DEV_DIR}" && MaaPiCli.exe'],
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
            )
            self._append_log("已在独立窗口打开原始 CLI。")
        except Exception as exc:
            messagebox.showerror("打开失败", str(exc))

    def _poll_messages(self) -> None:
        while True:
            try:
                kind, value = self.messages.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self._append_log(value)
            elif kind == "finished":
                self._set_running(False)
                if value == "0":
                    self._append_log("所选任务执行结束。")
                elif value == "2":
                    self._append_log("MAA 报告任务失败，请查看上方日志或模拟器当前页面。")
                else:
                    self._append_log(f"任务进程已结束，退出代码：{value}")
            elif kind == "connection":
                if value == "ok":
                    self.status_dot.configure(fg=SUCCESS)
                    self.connection_label.configure(text=f"MuMu 已连接 · {ADB_ADDRESS}")
                    self._append_log("模拟器连接正常。")
                else:
                    self.status_dot.configure(fg=DANGER)
                    self.connection_label.configure(text="未检测到 MuMu 设备")
                    self._append_log(f"未检测到 {ADB_ADDRESS}，请先启动模拟器。")
            elif kind == "connection_error":
                self.status_dot.configure(fg=DANGER)
                self.connection_label.configure(text="连接检查失败")
                self._append_log("连接检查失败：" + value)
        self.root.after(120, self._poll_messages)

    def _on_close(self) -> None:
        if self.is_running:
            if not messagebox.askyesno("任务正在运行", "关闭界面会同时停止当前任务，是否继续？"):
                return
            self._save_gui_settings()
            self._stop()
            self.root.after(600, self.root.destroy)
            return
        self._save_gui_settings()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    MaaQQReaderGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()
