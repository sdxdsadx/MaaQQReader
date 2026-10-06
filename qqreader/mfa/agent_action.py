"""MFAAvalonia Agent 自定义动作 ``QQReaderRunTask`` 的纯逻辑。

MFAAvalonia 把每个任务交给 Python Agent 的自定义动作；动作只做旧 GUI 串行
执行中的一步：先跑交接检查（``HandoffCheck``）确认现场，确认后再以子进程运行
``scripts/run_task.py --task <key>``，并把结果写进 ``daily_flows`` 记录。

本模块不导入 ``maa``（``mfa/agent/main.py`` 负责与 MaaFramework 对接），
所以可以在普通单元测试里用假 ``popen`` 完整覆盖。重复次数由 MFA 的
``repeat_count`` 处理，参数里的 ``count`` 被忽略。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple, Union
from uuid import uuid4

from ..config import ConfigError, load_config
from ..gui.commands import build_handoff_command, build_run_task_command, command_preview
from ..gui.task_catalog import DEFAULT_TASK_CATALOG, TaskSpec
from ..runner.exit_codes import (
    EXIT_BLOCKED_BY_CAPTCHA,
    EXIT_CANCELLED,
    EXIT_FAILED,
    EXIT_FATAL,
    EXIT_SUCCESS,
    describe_exit_code,
)
from ..workflow import (
    CHINA_TIMEZONE,
    DailyFlowRecorder,
    DailyFlowRun,
    FlowRunState,
    FlowStepRecord,
    FlowStepSnapshot,
    apply_handoff,
    business_day,
    handoff_report_path,
    load_handoff_report,
)

ACTION_NAME = "QQReaderRunTask"
DEFAULT_CONFIG_RELATIVE = Path("configs/qqreader.local.json")

#: 参数里允许出现但动作不处理的键（重复次数交给 MFA 的 repeat_count）。
_IGNORED_KEYS = frozenset({"count"})
#: MFA 未替换的占位符（例如输入框留空时原样传来的 ``{cover_image}``），按缺省处理。
_PLACEHOLDER_RE = re.compile(r"^\{[A-Za-z_][A-Za-z0-9_]*\}$")
_POLL_INTERVAL_SECONDS = 0.5
_KILL_WAIT_SECONDS = 10.0
_CONFIG_MISSING_MESSAGE = (
    "未找到本机配置或配置无效（{detail}）；请用 启动QQReaderGUI.cmd 启动，"
    "它会写入 configs/qqreader.local.json"
)


# ------------------------------------------------------------------ 参数


def parse_param(raw: Union[str, Mapping[str, Any]]) -> Tuple[TaskSpec, Dict[str, Any]]:
    """解析 MFA 传来的 ``custom_action_param``（JSON 字符串或字典）。

    返回任务描述与按 ``TaskSettingField.normalize`` 规整后的参数（未提供的、或仍是
    未替换占位符 ``{name}`` 的取默认值）。
    未知任务、未知键、取值非法都抛 ``ValueError``。
    """
    if isinstance(raw, Mapping):
        data: Any = dict(raw)
    else:
        text = str(raw or "").strip()
        if not text:
            raise ValueError("动作参数为空：必须提供 task")
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise ValueError(f"动作参数不是合法 JSON：{exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("动作参数必须是 JSON 对象")
    task = str(data.get("task") or "").strip()
    if not task:
        raise ValueError("动作参数缺少 task")
    spec = next((item for item in DEFAULT_TASK_CATALOG if item.key == task), None)
    if spec is None:
        raise ValueError(f"未知任务：{task}")
    field_keys = {item.key for item in spec.fields}
    unknown = sorted(
        str(key) for key in data if key != "task" and key not in field_keys and key not in _IGNORED_KEYS
    )
    if unknown:
        raise ValueError(f"任务 {task} 不支持参数：{', '.join(unknown)}")
    values: Dict[str, Any] = {}
    for item in spec.fields:
        if item.key in _IGNORED_KEYS:
            continue
        raw_value = data.get(item.key, item.default)
        if isinstance(raw_value, str) and _PLACEHOLDER_RE.fullmatch(raw_value.strip()):
            raw_value = item.default
        try:
            values[item.key] = item.normalize(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"参数「{item.label}」取值无效（{raw_value!r}）：{exc}") from exc
    return spec, values


# ------------------------------------------------------------------ 运行


@dataclass
class RunResult:
    success: bool
    exit_code: int
    message: str
    record_path: Optional[Path]


def _default_kill_tree(pid: int) -> None:
    """只结束本动作启动的进程树（按 PID，不按进程名）。"""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(int(pid)), "/T", "/F"],
            capture_output=True,
            check=False,
        )
    else:  # pragma: no cover - 本项目只在 Windows 上运行
        import signal

        os.kill(int(pid), signal.SIGTERM)


class _Cancelled(Exception):
    """用户在 MFA 中停止了任务。"""


class TaskRunner:
    """把一次 MFA 动作执行成「交接检查 → 任务子进程 → 记录」的单步流水线。"""

    def __init__(
        self,
        repo_root: Path,
        config_path: Path,
        *,
        popen: Callable[..., Any] = subprocess.Popen,
        log: Callable[[str], None] = print,
        is_stopping: Callable[[], bool] = lambda: False,
        kill_tree: Callable[[int], None] = _default_kill_tree,
        poll_interval: float = _POLL_INTERVAL_SECONDS,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.config_path = Path(config_path)
        self._popen = popen
        self._log = log
        self._is_stopping = is_stopping
        self._kill_tree = kill_tree
        self._poll_interval = max(0.0, float(poll_interval))

    # -------------------------------------------------------------- 主流程

    def run(self, spec: TaskSpec, values: Mapping[str, Any]) -> RunResult:
        try:
            config = load_config(self.config_path)
        except (ConfigError, OSError) as exc:
            message = _CONFIG_MISSING_MESSAGE.format(detail=exc)
            self._log(f"[QQReader] {message}")
            return RunResult(False, EXIT_FATAL, message, None)

        python = str(config.machine.python_executable or "") or sys.executable
        record_dir = Path(config.machine.record_dir)
        recorder = DailyFlowRecorder(record_dir)
        run = self._new_run(spec, values)
        record_path = self._save(recorder, run)
        self._log(f"[QQReader] run={run.run_id} 任务={spec.display_name} ({spec.key})")
        name = spec.display_name

        try:
            # 1) 交接检查：上一步留下的现场必须确认安全才能交给本任务。
            report_path = handoff_report_path(record_dir, run)
            handoff_command = build_handoff_command(
                python, self.repo_root, self.config_path, spec.key, report_path
            )
            self._log(f"[交接] 启动 {name} 前确认现场\n      {command_preview(handoff_command)}")
            handoff_code = self._run_process(handoff_command)
            report = load_handoff_report(report_path)
            started = apply_handoff(run, handoff_code, report)
            record_path = self._save(recorder, run) or record_path
            if started is None:
                if run.state is FlowRunState.BLOCKED_BY_CAPTCHA:
                    message = (
                        f"BLOCKED_BY_CAPTCHA：交接检查发现验证码，未启动 {name}；"
                        "不点击、不返回、不重启，等待人工处理"
                    )
                    self._log(f"[交接] {message}")
                    return RunResult(False, EXIT_BLOCKED_BY_CAPTCHA, message, record_path)
                reason = run.steps[0].reason
                message = f"{name} 未启动：{reason}"
                self._log(f"[交接] {message}")
                return RunResult(False, handoff_code, message, record_path)
            self._log(f"[交接] 现场已确认（{report.get('reason', '书架')}），启动 {name}")
            if self._is_stopping():
                raise _Cancelled()

            # 2) 任务子进程。
            try:
                task_command = build_run_task_command(
                    python, self.repo_root, self.config_path, spec.key, settings=dict(values)
                )
            except ValueError as exc:
                run.complete_current(EXIT_FAILED, reason=f"参数错误: {exc}")
                record_path = self._save(recorder, run) or record_path
                message = f"{name} 任务未成功：参数错误 {exc}"
                self._log(f"[QQReader] {message}")
                return RunResult(False, EXIT_FAILED, message, record_path)
            self._log(f"[任务] {name} 开始\n      {command_preview(task_command)}")
            code = self._run_process(task_command)
            run.complete_current(code)
            record_path = self._save(recorder, run) or record_path
        except _Cancelled:
            if run.state is FlowRunState.RUNNING:
                run.stop_by_user(reason="用户在 MFA 中停止任务")
            record_path = self._save(recorder, run) or record_path
            message = f"{name} 已停止（用户停止）"
            self._log(f"[QQReader] {message}")
            return RunResult(False, EXIT_CANCELLED, message, record_path)

        if code == EXIT_SUCCESS:
            message = f"{name} 成功"
            self._log(f"[QQReader] {message}")
            return RunResult(True, code, message, record_path)
        message = f"{name} 任务未成功：exit={code}（{describe_exit_code(code)}）"
        if code == EXIT_BLOCKED_BY_CAPTCHA:
            message += "；BLOCKED_BY_CAPTCHA，等待人工处理验证码"
        self._log(f"[QQReader] {message}")
        return RunResult(False, code, message, record_path)

    # -------------------------------------------------------------- 内部

    def _new_run(self, spec: TaskSpec, values: Mapping[str, Any]) -> DailyFlowRun:
        """单步流水线；步骤保持 WAITING，由交接检查结果决定是否启动。

        ``DailyFlowRun.start`` 会直接启动第一项（旧 GUI 的首项不做交接检查），
        这里每个 MFA 任务都先交接，所以直接构造运行对象。
        """
        now = datetime.now(timezone.utc)
        snapshot = FlowStepSnapshot.create(
            step_id=f"01-{spec.key}-1",
            task_key=spec.key,
            display_name=spec.display_name,
            settings=dict(values),
        )
        stamp = now.astimezone(CHINA_TIMEZONE).strftime("%Y%m%d_%H%M%S")
        return DailyFlowRun(
            run_id=f"mfa_{stamp}_{uuid4().hex[:8]}",
            business_day=business_day(now),
            captured_at=now,
            config_path=str(self.config_path),
            steps=[FlowStepRecord(snapshot)],
        )

    def _save(self, recorder: DailyFlowRecorder, run: DailyFlowRun) -> Optional[Path]:
        try:
            return recorder.save(run)
        except OSError as exc:
            self._log(f"[记录] 保存失败: {exc}")
            return None

    def _child_env(self) -> Dict[str, str]:
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        # stdout 是管道时 Python 默认块缓冲，输出会攒到子进程结束才进 MFA 日志。
        env["PYTHONUNBUFFERED"] = "1"
        root = str(self.repo_root)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = root + (os.pathsep + existing if existing else "")
        return env

    def _run_process(self, command: Sequence[str]) -> int:
        """启动子进程、转发输出并轮询等待；用户停止时只结束该进程树。"""
        if self._is_stopping():
            raise _Cancelled()
        try:
            process = self._popen(
                list(command),
                cwd=str(self.repo_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                env=self._child_env(),
            )
        except OSError as exc:
            # 与旧 GUI 一致：启动失败按退出码 1 处理。
            self._log(f"[启动失败] {exc}")
            return 1
        reader = threading.Thread(target=self._forward_output, args=(process,), daemon=True)
        reader.start()
        while True:
            code = process.poll()
            if code is not None:
                break
            if self._is_stopping():
                self._log(f"[停止] 结束进程 pid={process.pid}")
                try:
                    self._kill_tree(process.pid)
                except OSError as exc:
                    self._log(f"[停止失败] {exc}")
                try:
                    process.wait(timeout=_KILL_WAIT_SECONDS)
                except subprocess.TimeoutExpired:
                    self._log(f"[停止] 进程 pid={process.pid} 未在 {_KILL_WAIT_SECONDS:g} 秒内结束")
                reader.join(timeout=2.0)
                raise _Cancelled()
            time.sleep(self._poll_interval)
        reader.join(timeout=5.0)
        self._log(f"[进程结束] exit={code}")
        return int(code)

    def _forward_output(self, process: Any) -> None:
        stream = getattr(process, "stdout", None)
        if stream is None:
            return
        try:
            for raw in iter(stream.readline, b""):
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
                self._log(line.rstrip("\r\n"))
        except (OSError, ValueError) as exc:
            self._log(f"[输出读取中断] {exc}")


__all__ = [
    "ACTION_NAME",
    "DEFAULT_CONFIG_RELATIVE",
    "RunResult",
    "TaskRunner",
    "parse_param",
]
