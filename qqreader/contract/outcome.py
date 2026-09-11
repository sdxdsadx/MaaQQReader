"""任务运行结果与诊断记录。

AGENTS.md §3.9 要求日志/记录能区分
``SUCCESS / FAILED / TIMEOUT / BLOCKED_BY_CAPTCHA / SKIPPED``；
取消语义额外使用 ``CANCELLED``（取消不是失败）。
``DEVICE_ERROR`` 表示设备级失败（如 MAA 截屏级联失败 / adb 链路断开），
与任务逻辑失败 ``FAILED`` 区分。

QQR-10 还要求每次任务记录包含任务名、开始/结束时间、结果状态、失败原因
（含恢复尝试历史）与关键节点截图路径，因此本模块同时承载这些**纯数据**，
落盘策略由 :mod:`qqreader.runner.recording` 负责。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional, Tuple

from ..page.states import PageState, RunState


class TaskOutcome(str, Enum):
    """任务最终结果。"""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    DEVICE_ERROR = "DEVICE_ERROR"
    TIMEOUT = "TIMEOUT"
    BLOCKED_BY_CAPTCHA = "BLOCKED_BY_CAPTCHA"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class DiagnosticEvent:
    """一条可排障的事件记录。

    QQR-5 要求「识别失败必须产生诊断信息（尝试了哪些特征、各自结果）」，
    因此识别、恢复、验证码的每一步都会写入这里。
    """

    at: float
    kind: str
    message: str
    data: Mapping[str, Any] = field(default_factory=dict)

    def render(self) -> str:
        extra = " ".join(f"{k}={v!r}" for k, v in self.data.items())
        return f"[{self.at:10.3f}] {self.kind:<22} {self.message}" + (
            f" {extra}" if extra else ""
        )

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "at": self.at,
            "kind": self.kind,
            "message": self.message,
            "data": dict(self.data),
        }


@dataclass(frozen=True)
class KeyNodeScreenshot:
    """一个关键节点的截图证据。

    ``path`` 为空表示该节点截图失败/未提供；截图只是**证据**，不能作为
    任务成功依据（成功只由 ``success_condition`` 决定）。
    """

    kind: str
    at: float
    path: str = ""
    note: str = ""
    state: str = ""

    def render(self) -> str:
        target = self.path or "(未保存)"
        return f"[{self.at:10.3f}] {self.kind:<20} {target} {self.note}".rstrip()

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "kind": self.kind,
            "at": self.at,
            "path": self.path,
            "note": self.note,
            "state": self.state,
        }


@dataclass(frozen=True)
class RecoveryStep:
    """一次恢复尝试（QQR-10：失败原因必须含恢复尝试历史）。"""

    at: float
    attempt: int
    action: str
    reason: str
    description: str = ""
    targeted: bool = False

    def render(self) -> str:
        flag = "定向" if self.targeted else "升级"
        return (
            f"[{self.at:10.3f}] attempt={self.attempt} {flag} "
            f"{self.action} reason={self.reason!r} {self.description}".rstrip()
        )

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "at": self.at,
            "attempt": self.attempt,
            "action": self.action,
            "reason": self.reason,
            "description": self.description,
            "targeted": self.targeted,
        }


@dataclass(frozen=True)
class TaskResult:
    """一次任务执行的完整结果。"""

    task: str
    outcome: TaskOutcome
    reason: str
    started_at: float
    ended_at: float
    steps: int
    final_state: PageState
    run_state: RunState
    diagnostics: Tuple[DiagnosticEvent, ...] = ()
    #: QQR-10：关键节点截图（按发生顺序）。
    screenshots: Tuple[KeyNodeScreenshot, ...] = ()
    #: QQR-10：恢复尝试历史（含定向恢复）。
    recovery_history: Tuple[RecoveryStep, ...] = ()
    #: 落盘记录路径；未配置 recorder 或落盘失败时为 None。
    record_path: Optional[str] = None

    @property
    def duration(self) -> float:
        return max(0.0, self.ended_at - self.started_at)

    @property
    def succeeded(self) -> bool:
        return self.outcome is TaskOutcome.SUCCESS

    @property
    def blocked_by_captcha(self) -> bool:
        return self.outcome is TaskOutcome.BLOCKED_BY_CAPTCHA

    def summary(self) -> str:
        return (
            f"{self.task}: {self.outcome.value} ({self.reason}) "
            f"steps={self.steps} final_state={self.final_state.value} "
            f"run_state={self.run_state.value} duration={self.duration:.3f}s "
            f"screenshots={len(self.screenshots)} "
            f"recoveries={len(self.recovery_history)}"
        )

    def to_record(self) -> Mapping[str, Any]:
        """转换成可 JSON 序列化的记录（不依赖具体存储实现）。"""
        return {
            "record_version": 1,
            "task": self.task,
            "outcome": self.outcome.value,
            "reason": self.reason,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_seconds": self.duration,
            "steps": self.steps,
            "final_state": self.final_state.value,
            "run_state": self.run_state.value,
            "recovery_history": [step.to_dict() for step in self.recovery_history],
            "screenshots": [shot.to_dict() for shot in self.screenshots],
            "diagnostics": [event.to_dict() for event in self.diagnostics],
            "record_path": self.record_path,
        }
