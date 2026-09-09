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
        self._settings: Dict[str, TaskSettings] = default_settings(self._catalog)
        self._task_items: Dict[str, str] = {}
        self._item_specs: Dict[str, TaskSpec] = {}
        self._selected_spec: Optional[TaskSpec] = None
        self._field_vars: Dict[str, tk.Variable] = {}
        self._enabled_var = tk.BooleanVar(value=False)
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
        self.root.geometry("1180x760")
        self.root.minsize(960, 620)

        self._build_config_bar()
        self._build_toolbar()
        self._build_main_panes()
        self._build_status_bar()
        self.root.after(100, self._drain_log_queue)
        self._log("GUI 已启动。左侧勾选任务，右侧设置参数，点击「串行执行」。")

    def _build_config_bar(self) -> None:
        top = ttk.Frame(self.root, padding=(10, 8, 10, 4))
        top.pack(fill=tk.X)
        ttk.Label(top, text="配置文件").pack(side=tk.LEFT)
        self._config_var = tk.StringVar()
        ttk.Entry(top, textvariable=self._config_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 8)
        )
        ttk.Button(top, text="选择…", command=self._choose_config).pack(side=tk.LEFT)
        ttk.Button(top, text="加载", command=self._load_config_from_entry).pack(
            side=tk.LEFT, padx=(6, 0)
        )

    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self.root, padding=(10, 0, 10, 6))
        bar.pack(fill=tk.X)
        self._launch_button = ttk.Button(
            bar, text="启动模拟器", command=self._launch_emulator
        )
        self._launch_button.pack(side=tk.LEFT)
        self._serial_button = ttk.Button(
            bar, text="串行执行", command=self._run_serial
        )
        self._serial_button.pack(side=tk.LEFT, padx=(6, 0))
        self._selected_button = ttk.Button(
            bar, text="运行选中任务", command=self._run_selected
        )
        self._selected_button.pack(side=tk.LEFT, padx=(6, 0))
        self._stop_button = ttk.Button(
            bar, text="停止", command=self._stop_process, state=tk.DISABLED
        )
        self._stop_button.pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(
            bar, text="保存设置", command=self._save_settings
        ).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(
            bar, text="打开记录目录", command=self._open_record_dir
        ).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Label(bar, text="任务间隔").pack(side=tk.RIGHT)
        self._interval_var = tk.StringVar(value="3")
        ttk.Spinbox(
            bar, from_=0, to=120, increment=1, width=5,
            textvariable=self._interval_var,
        ).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Label(bar, text="秒").pack(side=tk.RIGHT)

    def _build_main_panes(self) -> None:
        paned = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))

        left = ttk.LabelFrame(paned, text="任务列表", padding=(6, 6))
        paned.add(left, weight=1)

        columns = ("enabled", "name")
        self._tree = ttk.Treeview(
            left,
            columns=columns,
            show="tree headings",
            selectmode="browse",
            height=18,
        )
        self._tree.heading("#0", text="分组 / 任务")
        self._tree.heading("enabled", text="启用")
        self._tree.heading("name", text="任务")
        self._tree.column("#0", width=230, stretch=True)
        self._tree.column("enabled", width=60, anchor=tk.CENTER, stretch=False)
        self._tree.column("name", width=150, stretch=True)
        tree_scroll = ttk.Scrollbar(
            left, orient=tk.VERTICAL, command=self._tree.yview
        )
        self._tree.configure(yscrollcommand=tree_scroll.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.bind("<<TreeviewSelect>>", self._on_select_task)
        self._tree.bind("<ButtonRelease-1>", self._on_tree_click)
        self._build_task_tree()

        right = ttk.Panedwindow(paned, orient=tk.VERTICAL)
        paned.add(right, weight=2)

        settings = ttk.LabelFrame(right, text="任务设置", padding=(8, 8))
        right.add(settings, weight=1)
        self._settings_desc = ttk.Label(
            settings, text="请选择一个任务", foreground="#555", wraplength=720
        )
        self._settings_desc.pack(anchor=tk.W, fill=tk.X)
        self._settings_body = ttk.Frame(settings)
        self._settings_body.pack(fill=tk.X, pady=(6, 0))

        log_frame = ttk.LabelFrame(right, text="实时日志", padding=(6, 6))
        right.add(log_frame, weight=3)
        self._log_text = tk.Text(log_frame, wrap=tk.WORD, height=18, state=tk.DISABLED)
        log_scroll = ttk.Scrollbar(
            log_frame, orient=tk.VERTICAL, command=self._log_text.yview
        )
        self._log_text.configure(yscrollcommand=log_scroll.set)
        self._log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_status_bar(self) -> None:
        bar = ttk.Frame(self.root, padding=(10, 0, 10, 8))
        bar.pack(fill=tk.X)
        ttk.Label(bar, text="状态：").pack(side=tk.LEFT)
        self._status_var = tk.StringVar(value="未运行")
        ttk.Label(
            bar, textvariable=self._status_var, foreground="#0a6"
        ).pack(side=tk.LEFT)
        self._current_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self._current_var).pack(side=tk.LEFT, padx=(16, 0))
        ttk.Button(bar, text="清空日志", command=self._clear_log).pack(side=tk.RIGHT)

    # ------------------------------------------------------------- 任务树

    def _build_task_tree(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._task_items.clear()
        self._item_specs.clear()
        groups: Dict[str, str] = {}
        for spec in self._catalog:
            if spec.group not in groups:
                group_iid = f"group:{spec.group}"
                groups[spec.group] = group_iid
                self._tree.insert(
                    "",
                    tk.END,
                    iid=group_iid,
                    text=f"▸ {spec.group}",
                    values=("", ""),
                    open=True,
                )
            enabled = self._settings[spec.key].enabled
            self._tree.insert(
                groups[spec.group],
                tk.END,
                iid=spec.key,
                text="",
                values=("☑" if enabled else "☐", spec.name),
            )
            self._task_items[spec.key] = spec.key
            self._item_specs[spec.key] = spec
        first = next(iter(self._item_specs), None)
        if first:
            self._tree.selection_set(first)
            self._tree.focus(first)

    def _on_tree_click(self, event: tk.Event) -> None:
        column = self._tree.identify_column(event.x)
        row = self._tree.identify_row(event.y)
        if column != "#1" or row not in self._item_specs:
            return
        self._toggle_task(row)

    def _on_select_task(self, _event: Optional[tk.Event] = None) -> None:
        selection = self._tree.selection()
        if not selection:
            return
        spec = self._item_specs.get(selection[0])
        if spec is None:
            self._settings_desc.configure(text=f"分组：{selection[0].split(':', 1)[-1]}")
            for child in self._settings_body.winfo_children():
                child.destroy()
            return
        self._selected_spec = spec
        self._show_settings(spec)

    def _toggle_task(self, key: str) -> None:
        settings = self._settings[key]
        settings.enabled = not settings.enabled
        self._tree.set(key, "enabled", "☑" if settings.enabled else "☐")
        self._log(f"[任务] {key} {'启用' if settings.enabled else '停用'}")
        self._save_settings(silent=True)

    def _refresh_task_item(self, spec: TaskSpec) -> None:
        if spec.key in self._task_items:
            self._tree.set(
                spec.key,
                "enabled",
                "☑" if self._settings[spec.key].enabled else "☐",
            )

    # ------------------------------------------------------------- 设置面板

    def _show_settings(self, spec: TaskSpec) -> None:
        self._settings_desc.configure(
            text=f"{spec.name}（{spec.key}）\n{spec.description}"
        )
        for child in self._settings_body.winfo_children():
            child.destroy()
        self._field_vars.clear()
        self._enabled_var.set(self._settings[spec.key].enabled)
        ttk.Checkbutton(
            self._settings_body,
            text="启用此任务",
            variable=self._enabled_var,
            command=lambda: self._on_enabled_changed(spec),
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 6))

        for row, item in enumerate(spec.fields, start=1):
            ttk.Label(self._settings_body, text=item.label).grid(
                row=row, column=0, sticky=tk.W, pady=2
            )
            current = self._settings[spec.key].value(spec, item.key)
            if item.kind == "bool":
                var: tk.Variable = tk.BooleanVar(value=bool(current))
                widget = ttk.Checkbutton(self._settings_body, variable=var)
            else:
                var = tk.StringVar(
                    value=f"{current:g}" if isinstance(current, float) else str(current)
                )
                widget = ttk.Spinbox(
                    self._settings_body,
                    from_=item.minimum if item.minimum is not None else 0,
                    to=item.maximum if item.maximum is not None else 999999,
                    increment=item.step,
                    width=12,
                    textvariable=var,
                )
            widget.grid(row=row, column=1, sticky=tk.W, padx=(10, 0), pady=2)
            if item.unit:
                ttk.Label(self._settings_body, text=item.unit).grid(
                    row=row, column=2, sticky=tk.W, padx=(6, 0)
                )
            self._field_vars[item.key] = var

    def _on_enabled_changed(self, spec: TaskSpec) -> None:
        self._settings[spec.key].enabled = bool(self._enabled_var.get())
        self._refresh_task_item(spec)

    def _collect_current_settings(self) -> bool:
        spec = self._selected_spec
        if spec is None:
            return True
        values = dict(self._settings[spec.key].values)
        try:
            for item in spec.fields:
                var = self._field_vars.get(item.key)
                if var is not None:
                    values[item.key] = item.normalize(var.get())
        except (tk.TclError, ValueError) as exc:
            messagebox.showwarning("参数错误", str(exc))
            return False
        self._settings[spec.key] = TaskSettings(
            enabled=bool(self._enabled_var.get()),
            values=values,
        )
        self._refresh_task_item(spec)
        return True

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
        self._settings = load_task_settings(self._settings_path(), self._catalog)
        self._build_task_tree()

    def _save_settings(self, *, silent: bool = False) -> None:
        if not self._collect_current_settings():
            return
        try:
            save_task_settings(self._settings_path(), self._settings, self._catalog)
        except OSError as exc:
            self._log(f"[设置] 保存失败: {exc}")
            return
        if not silent:
            self._log(f"[设置] 已保存到 {self._settings_path()}")

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
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=20,
                    check=False,
                )
                self._log(
                    f"[ADB] exit={result.returncode} "
                    f"{result.stdout.strip() or result.stderr.strip()}"
                )
            except (OSError, subprocess.SubprocessError) as exc:
                self._log(f"[ADB 错误] {exc}")

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
        self._serial_plan = build_serial_plan(self._settings, self._catalog)
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
        if not self._collect_current_settings():
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
        self._current_var.set(f"当前：{plan.spec.name} ({index}/{total})")
        self._log(
            f"[{index}/{total}] {plan.spec.name} ({plan.spec.key}) 开始\n"
            f"      {command_preview(command)}"
        )
        self._start_process(
            command,
            status=f"运行中：{plan.spec.name}",
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
                f"{plan.spec.name} 成功"
            )
        else:
            self._serial_failures += 1
            self._log(
                f"[{self._serial_index + 1}/{len(self._serial_plan)}] "
                f"{plan.spec.name} 失败 exit={code}"
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
        self._launch_button.configure(state=state)
        self._serial_button.configure(state=state)
        self._selected_button.configure(state=state)
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
        self._log_text.configure(state=tk.NORMAL)
        self._log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self._log_text.see(tk.END)
        self._log_text.configure(state=tk.DISABLED)

    def _set_status(self, text: str) -> None:
        self._status_var.set(text)


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
