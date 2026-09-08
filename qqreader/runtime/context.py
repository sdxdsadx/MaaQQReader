"""任务上下文与适配器协议。

``TaskContext`` 是条件、识别、适配器之间共享的可变状态；``TaskAdapter``
是**唯一**的领域行为入口（点击、滑动、等待等）。调度核心只调用
``adapter.advance`` / ``adapter.recover``，不关心具体是广告还是游戏。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, MutableMapping, Optional, Protocol, Tuple

from ..contract.contract import TaskContract
from ..page.observation import PageObservation
from ..page.recognizer import StateDecision
from ..page.states import PageState, RunState
from ..recovery.policy import RecoveryAction
from .clock import CancellationToken, Clock


@dataclass(frozen=True)
class StepResult:
    """适配器执行一步之后的自描述。"""

    description: str
    actions: Tuple[str, ...] = ()
    progress: bool = True
    data_updates: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def noop(cls, description: str = "无可执行动作") -> "StepResult":
        return cls(description=description, actions=(), progress=False)


class TaskAdapter(Protocol):
    """领域适配器：把「当前状态」翻译成一次安全动作。"""

    def advance(self, context: "TaskContext") -> StepResult:
        """执行一步推进（例如点击入口、等待广告、关闭结果页）。"""

    def recover(self, action: RecoveryAction, context: "TaskContext") -> StepResult:
        """执行一个恢复动作（例如关闭弹窗、返回、重启 App）。"""


@dataclass
class TaskContext:
    """一次任务执行的共享上下文。"""

    contract: TaskContract
    clock: Clock
    token: CancellationToken
    started_at: float
    observation: PageObservation = field(default_factory=PageObservation.empty)
    decision: Optional[StateDecision] = None
    step: int = 0
    run_state: RunState = RunState.IDLE
    data: MutableMapping[str, Any] = field(default_factory=dict)

    @property
    def now(self) -> float:
        return self.clock.now()

    @property
    def elapsed(self) -> float:
        return max(0.0, self.now - self.started_at)

    @property
    def state(self) -> PageState:
        return self.decision.state if self.decision is not None else PageState.UNKNOWN

    @property
    def state_confirmed(self) -> bool:
        return self.decision is not None and self.decision.is_confirmed

    def update_observation(
        self, observation: PageObservation, decision: StateDecision
    ) -> None:
        self.observation = observation
        self.decision = decision

    def update_data(self, **values: Any) -> None:
        self.data.update(values)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)
