from __future__ import annotations

import importlib
import json
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import qqreader_automation as core


BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "任务方案.json"
MODULE_NAMES = [
    "task_modules.start_emulator",
    "task_modules.start_reader",
    "task_modules.daily_game",
    "task_modules.daily_listening",
    "task_modules.daily_reading",
]


class TaskRow:
    def __init__(self, module, enabled=True, count=1, minutes=None, delay=None):
        self.module = module
        self.enabled = bool(enabled)
        self.count = max(1, int(count))
        default = getattr(module, "DEFAULT_MINUTES", 0)
        self.minutes = max(0, float(default if minutes is None else minutes))
        default_delay = getattr(module, "POST_DELAY_SECONDS", 0)
        self.delay = max(0, int(default_delay if delay is None else delay))

    @property
    def task_id(self):
        return self.module.TASK_ID


class AutomationGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("QQ 阅读自动任务面板")
        self.geometry("920x720")
        self.minsize(800, 620)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.events: queue.Queue = queue.Queue()
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.task_deadline = 0.0
        self.task_timer_total = 0

        modules = [importlib.import_module(name) for name in MODULE_NAMES]
        self.module_by_id = {module.TASK_ID: module for module in modules}
        self.tasks = [TaskRow(module) for module in modules]

        self.close_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="就绪")
        self.countdown_var = tk.StringVar(value="当前任务：未计时")

        self._build_ui()
        self.load_config(silent=True)
        self.refresh_tasks()
        self.after(100, self.process_events)

    def _build_ui(self):
        style = ttk.Style(self)
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 18, "bold"))
        style.configure("Task.TLabel", font=("Microsoft YaHei UI", 11, "bold"))

        top = ttk.Frame(self, padding=16)
        top.pack(fill="x")
        ttk.Label(top, text="QQ 阅读自动任务面板", style="Title.TLabel").pack(side="left")
        ttk.Label(top, textvariable=self.countdown_var, font=("Microsoft YaHei UI", 13)).pack(side="right")

        settings = ttk.LabelFrame(self, text="运行设置", padding=12)
        settings.pack(fill="x", padx=16, pady=(0, 10))
        ttk.Label(settings, text="每个任务的计时从进入对应界面后开始，默认 25 分钟。", foreground="#475569").pack(side="left")
        ttk.Checkbutton(
            settings, text="计时结束后关闭 MuMu 模拟器", variable=self.close_var
        ).pack(side="left")
        ttk.Button(settings, text="保存方案", command=self.save_config).pack(side="right")
        ttk.Button(settings, text="恢复默认", command=self.reset_default).pack(side="right", padx=8)

        middle = ttk.Panedwindow(self, orient="vertical")
        middle.pack(fill="both", expand=True, padx=16)

        task_box = ttk.LabelFrame(middle, text="任务顺序与重复次数", padding=8)
        middle.add(task_box, weight=3)

        header = ttk.Frame(task_box)
        header.pack(fill="x", pady=(0, 4))
        ttk.Label(header, text="启用", width=7).grid(row=0, column=0)
        ttk.Label(header, text="顺序", width=7).grid(row=0, column=1)
        ttk.Label(header, text="任务", width=25).grid(row=0, column=2, sticky="w")
        ttk.Label(header, text="次数", width=7).grid(row=0, column=3)
        ttk.Label(header, text="单次分钟", width=9).grid(row=0, column=4)
        ttk.Label(header, text="任务后间隔(秒)", width=14).grid(row=0, column=5)
        ttk.Label(header, text="调整", width=12).grid(row=0, column=6)

        self.rows_frame = ttk.Frame(task_box)
        self.rows_frame.pack(fill="both", expand=True)
        self.row_vars = []

        log_box = ttk.LabelFrame(middle, text="运行日志", padding=8)
        middle.add(log_box, weight=2)
        self.log_text = tk.Text(
            log_box, height=7, wrap="word", state="disabled",
            font=("Microsoft YaHei UI", 9), background="#111827", foreground="#e5e7eb",
        )
        scrollbar = ttk.Scrollbar(log_box, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        bottom = ttk.Frame(self, padding=16)
        # 重新按“底部优先、中间自适应”排列，确保控制按钮始终可见。
        middle.pack_forget()
        bottom.pack(side="bottom", fill="x")
        middle.pack(fill="both", expand=True, padx=16)
        self.progress = ttk.Progressbar(bottom, mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(0, 10))
        ttk.Label(bottom, textvariable=self.status_var).pack(side="left")
        self.start_button = ttk.Button(bottom, text="开始执行", command=self.start_run)
        self.start_button.pack(side="right")
        self.stop_button = ttk.Button(bottom, text="终止当前运行", command=self.stop_run, state="disabled")
        self.stop_button.pack(side="right", padx=8)
        ttk.Button(bottom, text="仅检查环境", command=self.start_check).pack(side="right")

    def refresh_tasks(self):
        for child in self.rows_frame.winfo_children():
            child.destroy()
        self.row_vars.clear()

        for index, task in enumerate(self.tasks):
            frame = ttk.Frame(self.rows_frame, padding=(4, 5))
            frame.pack(fill="x")
            enabled_var = tk.BooleanVar(value=task.enabled)
            count_var = tk.IntVar(value=task.count)
            minutes_var = tk.DoubleVar(value=task.minutes)
            delay_var = tk.IntVar(value=task.delay)
            self.row_vars.append((enabled_var, count_var, minutes_var, delay_var))
            ttk.Checkbutton(frame, variable=enabled_var).grid(row=0, column=0, padx=(10, 26))
            ttk.Label(frame, text=str(index + 1), width=5).grid(row=0, column=1)
            name = ttk.Label(frame, text=task.module.TASK_NAME, style="Task.TLabel", width=24)
            name.grid(row=0, column=2, sticky="w")
            ttk.Label(frame, text=task.module.DESCRIPTION, foreground="#64748b").grid(
                row=1, column=2, columnspan=3, sticky="w"
            )
            ttk.Spinbox(frame, from_=1, to=99, width=6, textvariable=count_var).grid(
                row=0, column=3, padx=10
            )
            if getattr(task.module, "DEFAULT_MINUTES", 0) > 0:
                ttk.Spinbox(
                    frame, from_=1, to=1440, increment=1, width=7, textvariable=minutes_var
                ).grid(row=0, column=4, padx=5)
            else:
                ttk.Label(frame, text="—", width=7, anchor="center").grid(row=0, column=4, padx=5)
            ttk.Spinbox(
                frame, from_=0, to=600, increment=1, width=7, textvariable=delay_var
            ).grid(row=0, column=5, padx=5)
            ttk.Button(frame, text="↑", width=4, command=lambda i=index: self.move_task(i, -1)).grid(
                row=0, column=6, padx=2
            )
            ttk.Button(frame, text="↓", width=4, command=lambda i=index: self.move_task(i, 1)).grid(
                row=0, column=7, padx=2
            )
            frame.columnconfigure(2, weight=1)

    def sync_rows(self):
        for task, (enabled_var, count_var, minutes_var, delay_var) in zip(self.tasks, self.row_vars):
            task.enabled = bool(enabled_var.get())
            try:
                task.count = max(1, int(count_var.get()))
            except (ValueError, tk.TclError):
                task.count = 1
            try:
                task.minutes = max(0, float(minutes_var.get()))
            except (ValueError, tk.TclError):
                task.minutes = float(getattr(task.module, "DEFAULT_MINUTES", 0))
            try:
                task.delay = max(0, int(delay_var.get()))
            except (ValueError, tk.TclError):
                task.delay = int(getattr(task.module, "POST_DELAY_SECONDS", 0))

    def move_task(self, index, delta):
        if self.worker and self.worker.is_alive():
            return
        self.sync_rows()
        target = index + delta
        if 0 <= target < len(self.tasks):
            self.tasks[index], self.tasks[target] = self.tasks[target], self.tasks[index]
            self.refresh_tasks()

    def plan_data(self):
        self.sync_rows()
        return {
            "close_emulator": bool(self.close_var.get()),
            "tasks": [
                {
                    "id": task.task_id,
                    "enabled": task.enabled,
                    "count": task.count,
                    "minutes": task.minutes,
                    "delay": task.delay,
                }
                for task in self.tasks
            ],
        }

    def save_config(self):
        try:
            CONFIG_FILE.write_text(json.dumps(self.plan_data(), ensure_ascii=False, indent=2), encoding="utf-8")
            self.append_log(f"方案已保存：{CONFIG_FILE.name}")
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))

    def load_config(self, silent=False):
        if not CONFIG_FILE.exists():
            return
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            self.close_var.set(bool(data.get("close_emulator", True)))
            loaded = []
            for item in data.get("tasks", []):
                module = self.module_by_id.get(item.get("id"))
                if module:
                    loaded.append(TaskRow(
                        module,
                        item.get("enabled", True),
                        item.get("count", 1),
                        item.get("minutes", getattr(module, "DEFAULT_MINUTES", 0)),
                        item.get("delay", getattr(module, "POST_DELAY_SECONDS", 0)),
                    ))
            if loaded:
                self.tasks = loaded
            if not silent:
                self.append_log("已载入保存的方案。")
        except Exception as exc:
            if not silent:
                messagebox.showerror("载入失败", str(exc))

    def reset_default(self):
        if self.worker and self.worker.is_alive():
            return
        self.tasks = [TaskRow(self.module_by_id[name.split(".")[-1]]) for name in MODULE_NAMES]
        self.close_var.set(True)
        self.refresh_tasks()
        self.append_log("已恢复默认顺序和次数。")

    def append_log(self, text):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text.rstrip() + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def emit_log(self, message):
        self.events.put(("log", message))

    def core_log(self, message):
        line = f"[{time.strftime('%H:%M:%S')}] {message}"
        self.emit_log(line)
        try:
            with core.LOG_FILE.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            pass

    def set_running(self, running):
        self.start_button.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")

    def start_check(self):
        if self.worker and self.worker.is_alive():
            return
        self.set_running(True)
        self.worker = threading.Thread(target=self.check_worker, daemon=True)
        self.worker.start()

    def check_worker(self):
        try:
            core.log = self.core_log
            core.set_timer_callback(self.timer_callback)
            core.validate_assets()
            core.ensure_emulator()
            self.events.put(("done", "环境检查通过"))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def start_run(self):
        try:
            plan = self.plan_data()
            if not any(item["enabled"] for item in plan["tasks"]):
                raise ValueError("请至少启用一个任务。")
            for item in plan["tasks"]:
                module = self.module_by_id[item["id"]]
                if item["enabled"] and getattr(module, "DEFAULT_MINUTES", 0) > 0 and item["minutes"] < 1:
                    raise ValueError(f"{module.TASK_NAME} 的单次计时不能少于 1 分钟。")
        except Exception as exc:
            messagebox.showwarning("无法开始", str(exc))
            return

        self.save_config()
        self.stop_event.clear()
        self.task_deadline = 0
        self.task_timer_total = 0
        self.progress["value"] = 0
        self.status_var.set("正在准备……")
        self.set_running(True)
        snapshot = [
            (task.module, task.enabled, task.count, task.minutes, task.delay)
            for task in self.tasks
        ]
        self.worker = threading.Thread(
            target=self.run_worker,
            args=(snapshot, plan["close_emulator"]),
            daemon=True,
        )
        self.worker.start()

    def run_worker(self, snapshot, close_after):
        try:
            core.log = self.core_log
            core.set_timer_callback(self.timer_callback)
            core.validate_assets()
            for module, enabled, count, minutes, delay in snapshot:
                if not enabled:
                    continue
                for repeat in range(1, count + 1):
                    if self.stop_event.is_set():
                        self.events.put(("stopped", None))
                        return
                    label = f"{module.TASK_NAME}（{repeat}/{count}）"
                    self.events.put(("status", label))
                    self.core_log(f"开始任务：{label}")
                    module.run(core, minutes, self.stop_event)
                    self.core_log(f"完成任务：{label}")
                    if delay > 0:
                        self.core_log(f"等待任务间隔：{delay} 秒")
                        if self.stop_event.wait(delay):
                            raise InterruptedError("用户已终止任务。")
            if close_after:
                core.close_emulator()
            self.events.put(("done", "全部任务完成"))
        except InterruptedError:
            self.events.put(("stopped", None))
        except Exception as exc:
            try:
                encoded, buffer = core.cv2.imencode(".png", core.screenshot())
                if encoded:
                    buffer.tofile(core.LAST_SCREEN)
            except Exception:
                pass
            self.events.put(("error", str(exc)))

    def stop_run(self):
        self.stop_event.set()
        self.stop_button.configure(state="disabled")
        self.status_var.set("正在停止……")
        self.append_log("已请求停止；当前点击步骤结束后停止，不会自动关闭模拟器。")

    def timer_callback(self, action, label, seconds):
        self.events.put(("timer", (action, label, seconds)))

    def update_running_countdown(self):
        if not self.task_deadline or not self.task_timer_total:
            return
        remaining = max(0, int(self.task_deadline - time.monotonic()))
        minutes, seconds = divmod(remaining, 60)
        self.countdown_var.set(f"当前任务剩余：{minutes:02d}:{seconds:02d}")
        elapsed = self.task_timer_total - remaining
        self.progress["value"] = min(100, elapsed * 100 / self.task_timer_total)

    def process_events(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
                    self.append_log(value)
                elif kind == "status":
                    self.status_var.set(value)
                elif kind == "done":
                    self.status_var.set(value)
                    self.progress["value"] = 100
                    self.set_running(False)
                    self.countdown_var.set("当前任务：未计时")
                    self.append_log(value)
                elif kind == "stopped":
                    self.status_var.set("已停止")
                    self.set_running(False)
                    self.task_deadline = 0
                    self.countdown_var.set("当前任务：已停止")
                elif kind == "error":
                    self.status_var.set("执行出错")
                    self.set_running(False)
                    self.task_deadline = 0
                    self.countdown_var.set("当前任务：出错")
                    self.append_log(f"错误：{value}")
                    messagebox.showerror("执行出错", f"{value}\n\n已停止后续任务，模拟器保持打开。")
                elif kind == "timer":
                    action, label, seconds = value
                    if action == "start":
                        self.task_timer_total = seconds
                        self.task_deadline = time.monotonic() + seconds
                        self.progress["value"] = 0
                        self.status_var.set(f"{label}计时中")
                    else:
                        self.task_deadline = 0
                        self.task_timer_total = 0
                        self.progress["value"] = 100
                        self.countdown_var.set("当前任务：计时完成")
        except queue.Empty:
            pass
        self.update_running_countdown()
        self.after(100, self.process_events)

    def on_close(self):
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno("任务仍在运行", "关闭面板会请求停止任务，是否关闭？"):
                return
            self.stop_event.set()
        self.destroy()


if __name__ == "__main__":
    AutomationGUI().mainloop()
