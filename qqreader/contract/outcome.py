"""任务运行结果与诊断记录。

AGENTS.md §3.9 要求日志/记录能区分
``SUCCESS / FAILED / TIMEOUT / BLOCKED_BY_CAPTCHA / SKIPPED``；
取消语义额外使用 ``CANCELLED``（取消不是失败）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Tuple

from ..page.states import PageState, RunState


class TaskOutcome(str, Enum):
    """任务最终结果。"""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
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


@dataclass(frozen=True)
class TaskResult:
    """一次任务执行的结果。"""

    task: str
    outcome: TaskOutcome
    reason: str
    started_at: float
    ended_at: float
    steps: int
    final_state: PageState
    run_state: RunState
    diagnostics: Tuple[DiagnosticEvent, ...] = ()

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
            f"run_state={self.run_state.value} duration={self.duration:.3f}s"
        )
