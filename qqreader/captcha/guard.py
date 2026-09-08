"""验证码层：检测后的阻塞、求解与**求解后确认**（AGENTS.md §3.8）。

关键约束：

* 检测到验证码后，正常任务推进暂停，进入 ``CAPTCHA`` 运行状态。
* 求解成功**必须重新观测确认验证码确实消失**，否则不算成功；
  「提交即认为通过」是禁止的。
* 无法自动处理时返回 ``WAITING_FOR_HUMAN``，任务结果为
  ``BLOCKED_BY_CAPTCHA``（不是 ``FAILED``）。
* 绝不把「求解失败」当作「没有验证码」继续执行。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Mapping, Optional, Protocol, Tuple

from ..contract.conditions import Condition
from ..page.observation import PageObservation
from ..page.recognizer import PageStateRecognizer
from ..page.states import PageState

if TYPE_CHECKING:  # pragma: no cover
    from ..runtime.context import TaskContext
    from ..runtime.observer import PageObserver


class CaptchaResolution(str, Enum):
    """验证码处理结论。"""

    SOLVED = "SOLVED"                      # 已确认验证码消失
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"  # 需要人工处理


@dataclass(frozen=True)
class SolveResult:
    """一次求解尝试的结果（由具体 solver 返回）。"""

    solved: bool
    reason: str
    data: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CaptchaOutcome:
    """验证码处理的完整结论，供调度核心记录诊断信息。"""

    resolution: CaptchaResolution
    attempts: int
    detail: str
    observations: Tuple[PageObservation, ...] = ()

    @property
    def solved(self) -> bool:
        return self.resolution is CaptchaResolution.SOLVED


class CaptchaSolver(Protocol):
    """验证码求解器协议（图片点选 / 滑块等）。"""

    def solve(self, context: "TaskContext") -> SolveResult:
        """尝试求解；只报告是否提交成功，是否真的通过由 guard 复核。"""


class CaptchaGuard(Protocol):
    """验证码守卫协议。"""

    def handle(self, context: "TaskContext") -> CaptchaOutcome:
        """阻塞正常流程，处理验证码。"""


class ManualCaptchaGuard:
    """无法自动求解时的守卫：直接进入等待人工。"""

    def handle(self, context: "TaskContext") -> CaptchaOutcome:
        return CaptchaOutcome(
            resolution=CaptchaResolution.WAITING_FOR_HUMAN,
            attempts=0,
            detail="未配置自动求解器，等待人工处理验证码",
        )


class VerifyingCaptchaGuard:
    """「求解 → 重新观测确认消失」的守卫。

    只有连续观测到验证码状态消失，才返回 ``SOLVED``；否则最多尝试
    ``max_attempts`` 次后进入等待人工。
    """

    def __init__(
        self,
        solver: CaptchaSolver,
        observer: "PageObserver",
        recognizer: PageStateRecognizer,
        captcha_condition: Condition,
        max_attempts: int = 2,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts 必须 >= 1")
        self._solver = solver
        self._observer = observer
        self._recognizer = recognizer
        self._captcha_condition = captcha_condition
        self._max_attempts = max_attempts

    def handle(self, context: "TaskContext") -> CaptchaOutcome:
        observations = []
        details = []
        for attempt in range(1, self._max_attempts + 1):
            result = self._solver.solve(context)
            details.append(f"第 {attempt} 次求解: {result.reason}")
            if not result.solved:
                return CaptchaOutcome(
                    resolution=CaptchaResolution.WAITING_FOR_HUMAN,
                    attempts=attempt,
                    detail="; ".join(details),
                    observations=tuple(observations),
                )
            # 求解器只是「提交成功」；必须重新观测确认验证码确实消失。
            observation = self._observer.observe(context)
            decision = self._recognizer.evaluate(observation)
            context.update_observation(observation, decision)
            observations.append(observation)
            still_present = (
                decision.state is PageState.CAPTCHA
                or self._captcha_condition.evaluate(context).satisfied
            )
            if not still_present:
                details.append(f"第 {attempt} 次求解后已确认验证码消失")
                return CaptchaOutcome(
                    resolution=CaptchaResolution.SOLVED,
                    attempts=attempt,
                    detail="; ".join(details),
                    observations=tuple(observations),
                )
            details.append(f"第 {attempt} 次求解后验证码仍然存在，拒绝当作已通过")
        return CaptchaOutcome(
            resolution=CaptchaResolution.WAITING_FOR_HUMAN,
            attempts=self._max_attempts,
            detail="; ".join(details),
            observations=tuple(observations),
        )
