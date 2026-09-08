"""任务定义：把「契约」与「执行协作对象」绑定起来。

``TaskContract`` 保持纯数据；``TaskDefinition`` 负责注入具体实现
（观测器、适配器、恢复策略、验证码守卫、状态识别器）。这样调度核心只认
契约，不认任务名。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..captcha.guard import CaptchaGuard
from ..contract.contract import TaskContract
from ..errors import ContractViolation
from ..page.recognizer import PageStateRecognizer
from ..recovery.policy import RecoveryStrategy
from ..runtime.context import TaskAdapter
from ..runtime.observer import PageObserver


@dataclass(frozen=True)
class TaskDefinition:
    """一个可执行任务的完整装配。"""

    contract: TaskContract
    observer: PageObserver
    adapter: TaskAdapter
    recovery: RecoveryStrategy
    captcha_guard: CaptchaGuard
    state_recognizer: PageStateRecognizer

    def __post_init__(self) -> None:
        if not isinstance(self.contract, TaskContract):
            raise ContractViolation("TaskDefinition.contract 必须是 TaskContract")

    @property
    def name(self) -> str:
        return self.contract.name
