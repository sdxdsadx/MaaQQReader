"""Tkinter GUI：加载配置、启动 MuMu、运行新的 DailyGameFlow 脚本。"""

from __future__ import annotations

import argparse
import os
import queue
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..config import AppConfig, ConfigError, load_config
from .commands import (
    build_adb_connect_command,
    build_emulator_launch_command,
    build_run_game_flow_command,
    command_preview,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


class QQReaderGui:
    """最小可用 GUI：配置 + 启动模拟器 + 运行/停止脚本 + 实时日志。"""

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
        self._log_queue: "queue.Queue[str]" = queue.Queue()
        self._build_ui()
        if config_path is not None:
            self._load_config(Path(config_path))

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        self.root.title("QQReader 每日任务控制台")
        self.root.geometry("980x680")
        self.root.minsize(820, 560)

        top = ttk.Frame(self.root, padding=(10, 8))
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

        controls = ttk.LabelFrame(self.root, text="任务控制", padding=(10, 8))
        controls.pack(fill=tk.X, padx=10, pady=(0, 8))
        ttk.Label(controls, text="挂机分钟").grid(row=0, column=0, sticky=tk.W)
        self._duration_var = tk.StringVar(value="22")
        ttk.Spinbox(
            controls, from_=0.02, to=180, increment=1, width=8,
            textvariable=self._duration_var,
        ).grid(row=0, column=1, padx=(6, 16))
        ttk.Label(controls, text="超时分钟").grid(row=0, column=2, sticky=tk.W)
        self._timeout_var = tk.StringVar(value="30")
        ttk.Spinbox(
            controls, from_=0.1, to=240, increment=1, width=8,
            textvariable=self._timeout_var,
        ).grid(row=0, column=3, padx=(6, 16))

        self._launch_button = ttk.Button(
            controls, text="启动模拟器", command=self._launch_emulator
        )
        self._launch_button.grid(row=0, column=4, padx=(0, 6))
        self._run_button = ttk.Button(
            controls, text="运行游戏流程", command=self._run_game_flow
        )
        self._run_button.grid(row=0, column=5, padx=(0, 6))
        self._stop_button = ttk.Button(
            controls, text="停止", command=self._stop_process, state=tk.DISABLED
        )
        self._stop_button.grid(row=0, column=6, padx=(0, 6))
        ttk.Button(
            controls, text="打开记录目录", command=self._open_record_dir
        ).grid(row=0, column=7)

        status_bar = ttk.Frame(self.root, padding=(10, 0))
        status_bar.pack(fill=tk.X)
        ttk.Label(status_bar, text="状态：").pack(side=tk.LEFT)
        self._status_var = tk.StringVar(value="未运行")
        ttk.Label(
            status_bar, textvariable=self._status_var, foreground="#0a6"
        ).pack(side=tk.LEFT)
        ttk.Button(status_bar, text="清空日志", command=self._clear_log).pack(
            side=tk.RIGHT
        )

        log_frame = ttk.LabelFrame(self.root, text="实时日志", padding=(6, 6))
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self._log_text = tk.Text(
            log_frame, wrap=tk.WORD, height=20, state=tk.DISABLED
        )
        scroll = ttk.Scrollbar(
            log_frame, orient=tk.VERTICAL, command=self._log_text.yview
        )
        self._log_text.configure(yscrollcommand=scroll.set)
        self._log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.root.after(100, self._drain_log_queue)
        self._log("GUI 已启动。请先选择并加载本机配置文件。")

    # ------------------------------------------------------------------ 配置

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
        self._set_status("未运行")

    def _require_config(self) -> Optional[AppConfig]:
        if self._config is None:
            messagebox.showwarning("配置", "请先加载本机配置文件")
            return None
        return self._config

    # ------------------------------------------------------------------ 模拟器

    def _launch_emulator(self) -> None:
        config = self._require_config()
        if config is None or self._busy:
            return
        emulator = config.machine.emulator_path
        if not emulator:
            messagebox.showwarning(
                "模拟器", "配置里没有 machine.emulator_path"
            )
            return
        try:
            command = build_emulator_launch_command(Path(emulator))
        except ValueError as exc:
            self._log(f"[模拟器错误] {exc}")
            return
        self._log("[模拟器] " + command_preview(command))
        self._start_process(
            command,
            status="启动模拟器",
            on_finish=self._connect_adb_after_launch,
        )

    def _connect_adb_after_launch(self) -> None:
        config = self._config
        if config is None:
            return
        adb_path = config.machine.adb_path
        address = config.machine.adb_address
        command = build_adb_connect_command(adb_path, address)
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

    # ------------------------------------------------------------------ 运行

    def _run_game_flow(self) -> None:
        config = self._require_config()
        if config is None or self._busy:
            return
        try:
            duration = float(self._duration_var.get())
            timeout = float(self._timeout_var.get())
        except ValueError:
            messagebox.showwarning("参数", "挂机分钟/超时分钟必须是数字")
            return
        try:
            command = build_run_game_flow_command(
                sys.executable,
                self.repo_root,
                Path(self._config_var.get()),
                duration_minutes=duration,
                timeout_minutes=timeout,
            )
        except ValueError as exc:
            messagebox.showwarning("参数", str(exc))
            return
        self._log("[运行] " + command_preview(command))
        self._start_process(command, status="运行中")

    def _start_process(
        self,
        command: Sequence[str],
        *,
        status: str,
        on_finish=None,
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
            return
        self._process = process
        self._busy = True
        self._stopping = False
        self._set_status(status)
        self._stop_button.configure(state=tk.NORMAL)
        self._run_button.configure(state=tk.DISABLED)
        self._launch_button.configure(state=tk.DISABLED)
        threading.Thread(
            target=self._read_process_output,
            args=(process, on_finish),
            daemon=True,
        ).start()

    def _read_process_output(self, process: subprocess.Popen, on_finish) -> None:
        if process.stdout is not None:
            for line in process.stdout:
                self._log_queue.put(line.rstrip("\n"))
        code = process.wait()
        self._log_queue.put(f"[进程结束] exit={code}")
        self._log_queue.put(f"__PROCESS_FINISHED__:{code}")
        if on_finish is not None:
            on_finish()

    def _drain_log_queue(self) -> None:
        while True:
            try:
                line = self._log_queue.get_nowait()
            except queue.Empty:
                break
            if line.startswith("__PROCESS_FINISHED__:"):
                code = int(line.split(":", 1)[1])
                self._on_process_finished(code)
            else:
                self._log(line)
        self.root.after(100, self._drain_log_queue)

    def _on_process_finished(self, code: int) -> None:
        was_stopping = self._stopping
        self._stopping = False
        self._busy = False
        self._process = None
        self._stop_button.configure(state=tk.DISABLED)
        self._run_button.configure(state=tk.NORMAL)
        self._launch_button.configure(state=tk.NORMAL)
        if was_stopping:
            self._set_status("已停止")
        else:
            self._set_status("已完成" if code == 0 else f"失败(exit={code})")

    def _stop_process(self) -> None:
        process = self._process
        if process is None or process.poll() is not None:
            return
        self._stopping = True
        self._log("[停止] 正在结束子进程…")
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                )
            else:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        except OSError as exc:
            self._log(f"[停止失败] {exc}")
        self._set_status("已停止")

    # ------------------------------------------------------------------ 其它

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
