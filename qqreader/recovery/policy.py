"""恢复层：升级式兜底策略（AGENTS.md §3.7）。

升级顺序：

    重新截图 → 重新判断当前状态 → 关闭普通弹窗 → 返回一次
    → 重新进入当前任务入口 → 重启 QQ 阅读 → 必要时重启模拟器 → 任务失败

重要边界：

* **验证码状态禁止进入普通 Recovery**。该约束由调度核心强制（检测到
  ``CAPTCHA`` 时只走验证码流程），本模块不提供任何「返回/重启绕过验证码」的动作。
* 恢复动作只是**决策**；具体怎么执行由适配器实现。恢复次数耗尽不等于立刻
  失败——只有「恢复耗尽 + 独立超时」才标记 ``FAILED``（§3.9）。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, Tuple

from ..errors import ContractViolation


class RecoveryAction(str, Enum):
    """恢复动作。"""

    RESCREENSHOT = "RESCREENSHOT"
    REEVALUATE_STATE = "REEVALUATE_STATE"
    DISMISS_POPUP = "DISMISS_POPUP"
    PRESS_BACK = "PRESS_BACK"
    REENTER_TASK_ENTRY = "REENTER_TASK_ENTRY"
    RESTART_APP = "RESTART_APP"
    RESTART_EMULATOR = "RESTART_EMULATOR"
    GIVE_UP = "GIVE_UP"


#: 默认升级阶梯（不含终止动作 GIVE_UP）。
DEFAULT_ESCALATION: Tuple[RecoveryAction, ...] = (
    RecoveryAction.RESCREENSHOT,
    RecoveryAction.REEVALUATE_STATE,
    RecoveryAction.DISMISS_POPUP,
    RecoveryAction.PRESS_BACK,
    RecoveryAction.REENTER_TASK_ENTRY,
    RecoveryAction.RESTART_APP,
    RecoveryAction.RESTART_EMULATOR,
)


class RecoveryStrategy(Protocol):
    """恢复策略协议。"""

    def next_action(self, attempt: int) -> RecoveryAction:
        """第 ``attempt`` 次恢复（从 0 开始）应执行的动作。"""

    def exhausted(self, attempt: int) -> bool:
        """恢复阶梯是否已耗尽。"""


@dataclass(frozen=True)
class EscalationPolicy:
    """按固定阶梯轮转的恢复策略。

    ``max_rounds`` 表示完整走几遍阶梯；走完仍无法恢复则 ``exhausted``。
    """

    ladder: Tuple[RecoveryAction, ...] = DEFAULT_ESCALATION
    max_rounds: int = 2
    allow_emulator_restart: bool = False

    def __post_init__(self) -> None:
        if not self.ladder:
            raise ContractViolation("恢复阶梯不能为空")
        if RecoveryAction.GIVE_UP in self.ladder:
            raise ContractViolation("GIVE_UP 是终止动作，不应出现在恢复阶梯中")
        if self.max_rounds < 1:
            raise ContractViolation("max_rounds 必须 >= 1")

    @property
    def usable_ladder(self) -> Tuple[RecoveryAction, ...]:
        if self.allow_emulator_restart:
            return self.ladder
        return tuple(a for a in self.ladder if a is not RecoveryAction.RESTART_EMULATOR)

    def next_action(self, attempt: int) -> RecoveryAction:
        if attempt < 0:
            raise ValueError("attempt 不能为负")
        ladder = self.usable_ladder
        if self.exhausted(attempt):
            return RecoveryAction.GIVE_UP
        return ladder[attempt % len(ladder)]

    def exhausted(self, attempt: int) -> bool:
        return attempt >= self.max_rounds * len(self.usable_ladder)

    def describe(self) -> str:
        return (
            " → ".join(a.value for a in self.usable_ladder)
            + f" → {RecoveryAction.GIVE_UP.value}（最多 {self.max_rounds} 轮）"
        )


@dataclass(frozen=True)
class RecoveryRecord:
    """一次恢复动作的记录。"""

    attempt: int
    action: RecoveryAction
    reason: str
    detail: str = ""
