"""声明式动作计划与适配器。

专属行为（点哪个特征、等多久、按返回）以**数据**形式放在这里，调度核心
不做任何任务名判断。安全边界：

* ``UNKNOWN`` 状态**绝不**盲目点击，只能重新观察；
* 只有 ``START`` 阶段且尚未引导过时，才允许启动目标 App；
* 恢复动作由 :class:`~qqreader.recovery.policy.RecoveryAction` 映射而来。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional, Tuple

from ..errors import ContractViolation
from ..page.states import PageState
from ..recovery.policy import RecoveryAction
from ..runner.runner import PHASE_KEY, RunPhase
from ..runtime.context import StepResult, TaskContext
from ..runtime.device import DeviceController


class ActionKind(str, Enum):
    """动作种类。"""

    TAP_FEATURE = "TAP_FEATURE"
    TAP_POINT = "TAP_POINT"
    PRESS_BACK = "PRESS_BACK"
    LAUNCH_APP = "LAUNCH_APP"
    STOP_APP = "STOP_APP"
    RESTART_APP = "RESTART_APP"
    WAIT = "WAIT"
    SWIPE = "SWIPE"
    REOBSERVE = "REOBSERVE"
    NOOP = "NOOP"


@dataclass(frozen=True)
class Action:
    """一个原子动作。"""

    kind: ActionKind
    target: str = ""
    seconds: float = 0.0
    x: int = 0
    y: int = 0
    x2: int = 0
    y2: int = 0
    duration_ms: int = 300

    def __post_init__(self) -> None:
        if self.kind is ActionKind.WAIT and self.seconds < 0:
            raise ContractViolation("WAIT.seconds 不能为负")
        if self.kind in (
            ActionKind.TAP_FEATURE,
            ActionKind.LAUNCH_APP,
            ActionKind.STOP_APP,
            ActionKind.RESTART_APP,
        ) and not self.target:
            raise ContractViolation(f"{self.kind.value} 必须提供 target")

    @property
    def label(self) -> str:
        if self.target:
            return f"{self.kind.value}:{self.target}"
        if self.kind is ActionKind.WAIT:
            return f"WAIT:{self.seconds:g}s"
        return self.kind.value

    # --- 构造器 ---
    @classmethod
    def tap_feature(cls, target: str) -> "Action":
        return cls(ActionKind.TAP_FEATURE, target=target)

    @classmethod
    def tap_point(cls, x: int, y: int) -> "Action":
        return cls(ActionKind.TAP_POINT, x=x, y=y)

    @classmethod
    def press_back(cls) -> "Action":
        return cls(ActionKind.PRESS_BACK)

    @classmethod
    def launch_app(cls, package: str) -> "Action":
        return cls(ActionKind.LAUNCH_APP, target=package)

    @classmethod
    def stop_app(cls, package: str) -> "Action":
        return cls(ActionKind.STOP_APP, target=package)

    @classmethod
    def restart_app(cls, package: str) -> "Action":
        return cls(ActionKind.RESTART_APP, target=package)

    @classmethod
    def wait(cls, seconds: float) -> "Action":
        return cls(ActionKind.WAIT, seconds=seconds)

    @classmethod
    def swipe(cls, x0: int, y0: int, x1: int, y1: int, duration_ms: int = 300) -> "Action":
        return cls(ActionKind.SWIPE, x=x0, y=y0, x2=x1, y2=y1, duration_ms=duration_ms)

    @classmethod
    def reobserve(cls) -> "Action":
        return cls(ActionKind.REOBSERVE)

    @classmethod
    def noop(cls) -> "Action":
        return cls(ActionKind.NOOP)


@dataclass(frozen=True)
class StateActionPlan:
    """页面状态 → 动作 的声明式映射。"""

    actions: Mapping[PageState, Action]
    unknown_action: Action = field(default_factory=Action.reobserve)
    bootstrap_action: Optional[Action] = None

    def action_for(self, state: PageState) -> Action:
        return self.actions.get(state, self.unknown_action)


class PlannedTaskAdapter:
    """按 :class:`StateActionPlan` 执行的通用适配器。"""

    def __init__(
        self,
        device: DeviceController,
        plan: StateActionPlan,
        expected_package: str,
        popup_feature: str = "popup.close",
        recovery_actions: Optional[Mapping[RecoveryAction, Action]] = None,
    ) -> None:
        self._device = device
        self._plan = plan
        self._expected_package = expected_package
        defaults = {
            RecoveryAction.RESCREENSHOT: Action.reobserve(),
            RecoveryAction.REEVALUATE_STATE: Action.reobserve(),
            RecoveryAction.DISMISS_POPUP: Action.tap_feature(popup_feature),
            RecoveryAction.PRESS_BACK: Action.press_back(),
            RecoveryAction.REENTER_TASK_ENTRY: Action.launch_app(expected_package),
            RecoveryAction.RESTART_APP: Action.restart_app(expected_package),
            RecoveryAction.RESTART_EMULATOR: Action.noop(),
        }
        if recovery_actions:
            defaults.update(recovery_actions)
        self._recovery_actions = defaults

    # ------------------------------------------------------------------ 协议

    def advance(self, context: TaskContext) -> StepResult:
        if context.decision is None:
            return StepResult("尚未观测，重新观察", actions=(ActionKind.REOBSERVE.value,), progress=False)
        state = context.decision.state
        if state is PageState.UNKNOWN:
            # 状态未确认时绝不点击。仅在 START 阶段、尚未引导过时启动目标 App。
            if (
                self._plan.bootstrap_action is not None
                and context.get(PHASE_KEY) == RunPhase.START.value
                and not context.get("adapter_bootstrapped")
            ):
                context.update_data(adapter_bootstrapped=True)
                return self._execute(self._plan.bootstrap_action, context)
            return StepResult(
                "页面状态未确认，重新观察（不点击）",
                actions=(ActionKind.REOBSERVE.value,),
                progress=False,
            )
        context.update_data(adapter_bootstrapped=True)
        return self._execute(self._plan.action_for(state), context)

    def recover(self, action: RecoveryAction, context: TaskContext) -> StepResult:
        return self._execute(self._recovery_actions.get(action, Action.reobserve()), context)

    # ------------------------------------------------------------------ 执行

    def _execute(self, action: Action, context: TaskContext) -> StepResult:
        kind = action.kind
        if kind is ActionKind.REOBSERVE:
            return StepResult(
                "重新观察页面（不点击）",
                actions=(kind.value,),
                progress=False,
            )
        if kind is ActionKind.NOOP:
            return StepResult.noop("无动作")
        if kind is ActionKind.WAIT:
            context.clock.sleep(action.seconds, context.token)
            return StepResult(
                f"等待 {action.seconds:g}s",
                actions=(kind.value,),
                progress=True,
            )
        if kind is ActionKind.TAP_FEATURE:
            ok = self._device.tap_feature(action.target)
            message = (
                f"点击特征 {action.target}"
                if ok
                else f"未定位到特征 {action.target}，保持当前页面"
            )
            return StepResult(
                message,
                actions=(f"{kind.value}:{action.target}",),
                progress=ok,
            )
        if kind is ActionKind.TAP_POINT:
            self._device.tap_point(action.x, action.y)
            return StepResult(
                f"点击坐标 ({action.x}, {action.y})",
                actions=(kind.value,),
                progress=True,
            )
        if kind is ActionKind.PRESS_BACK:
            self._device.press_back()
            return StepResult("按返回键", actions=(kind.value,), progress=True)
        if kind is ActionKind.LAUNCH_APP:
            self._device.launch_app(action.target)
            return StepResult(
                f"启动应用 {action.target}",
                actions=(f"{kind.value}:{action.target}",),
                progress=True,
            )
        if kind is ActionKind.STOP_APP:
            self._device.stop_app(action.target)
            return StepResult(
                f"停止应用 {action.target}",
                actions=(f"{kind.value}:{action.target}",),
                progress=True,
            )
        if kind is ActionKind.RESTART_APP:
            self._device.stop_app(action.target)
            self._device.launch_app(action.target)
            return StepResult(
                f"重启应用 {action.target}",
                actions=(f"{kind.value}:{action.target}",),
                progress=True,
            )
        if kind is ActionKind.SWIPE:
            self._device.swipe(
                action.x, action.y, action.x2, action.y2, action.duration_ms
            )
            return StepResult(
                f"滑动 ({action.x},{action.y})→({action.x2},{action.y2})",
                actions=(kind.value,),
                progress=True,
            )
        raise ContractViolation(f"未知动作: {kind}")  # pragma: no cover
