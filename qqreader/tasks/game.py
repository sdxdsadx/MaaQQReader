"""游戏任务契约与适配器（AGENTS.md §3.5）。

流程：``进入游戏 → 确认游戏真正启动 → 确认横竖屏 → 挂机（默认 25 分钟）→
周期性检查状态 → 退出 → 返回奖励页确认完成``。
"""

from __future__ import annotations

from typing import Optional

from ..captcha.guard import CaptchaGuard, ManualCaptchaGuard
from ..contract.conditions import StateIs, all_of, feature, state_in
from ..contract.contract import TaskContract, TimeoutSpec
from ..page.feature_keys import DEFAULT_FEATURE_KEYS, FeatureKeys
from ..page.features import MatchMode
from ..page.recognizer import PageStateRecognizer
from ..page.states import PageState
from ..recovery.policy import RecoveryStrategy
from ..runner.definition import TaskDefinition
from ..runtime.context import StepResult, TaskContext
from ..runtime.device import DeviceController
from ..runtime.observer import PageObserver
from .common import (
    captcha_condition,
    health_fatal_errors,
    ocr,
    popup_recoverable,
    wrong_page_recoverable,
)
from .plan import Action, PlannedTaskAdapter, StateActionPlan

GAME_TASK_NAME = "DailyGameFlow"
DEFAULT_GAME_TIMEOUT_SECONDS = 30 * 60
DEFAULT_GAME_DURATION_SECONDS = 25 * 60


def build_game_contract(
    keys: FeatureKeys = DEFAULT_FEATURE_KEYS,
    *,
    timeout_seconds: float = DEFAULT_GAME_TIMEOUT_SECONDS,
    timeout_label: str = "游戏任务独立超时",
) -> TaskContract:
    """构造游戏任务的 8 字段契约。"""
    return TaskContract(
        name=GAME_TASK_NAME,
        description="游戏挂机：进入游戏 → 确认运行 → 挂机 → 退出 → 奖励页确认",
        start_condition=state_in(PageState.HOME, PageState.REWARD_HOME),
        ready_condition=state_in(PageState.GAME_LOADING, PageState.GAME_RUNNING),
        progress_condition=state_in(
            PageState.GAME_LOADING,
            PageState.GAME_RUNNING,
            PageState.GAME_RESULT,
            PageState.REWARD_HOME,
        ),
        captcha_condition=captcha_condition(keys),
        success_condition=all_of(
            StateIs(PageState.REWARD_HOME),
            feature(ocr(keys.game_success_regex, mode=MatchMode.REGEX)),
        ),
        recoverable_error=(
            popup_recoverable(keys),
            wrong_page_recoverable(
                "wrong_page_game",
                (PageState.AD_PLAYING, PageState.AD_RESULT),
                "误入广告页面，返回奖励页",
            ),
        ),
        fatal_error=health_fatal_errors(keys),
        timeout=TimeoutSpec(timeout_seconds, timeout_label),
    )


def build_game_action_plan(keys: FeatureKeys = DEFAULT_FEATURE_KEYS) -> StateActionPlan:
    """游戏任务的状态 → 动作计划。"""
    return StateActionPlan(
        actions={
            PageState.HOME: Action.tap_feature(keys.game_entry),
            PageState.REWARD_HOME: Action.tap_feature(keys.game_entry),
            PageState.GAME_LOADING: Action.tap_feature(keys.game_ocr_enter_alt),
            PageState.GAME_RUNNING: Action.wait(10.0),
            PageState.GAME_RESULT: Action.tap_feature(keys.game_ocr_exit),
            # 误入广告页面时先返回；真正的恢复由 recoverable_error 驱动。
            PageState.AD_PLAYING: Action.press_back(),
            PageState.AD_RESULT: Action.press_back(),
        },
        unknown_action=Action.reobserve(),
        bootstrap_action=Action.launch_app(keys.qq_reader_package),
    )


class GameTaskAdapter(PlannedTaskAdapter):
    """带挂机计时的游戏适配器。

    只有确认进入 ``GAME_RUNNING`` 后才开始计时；达到 ``game_duration_seconds``
    后主动执行退出动作。计时状态放在 ``TaskContext.data``，不污染契约。
    """

    def __init__(
        self,
        *,
        game_duration_seconds: float,
        exit_action: Action,
        device: DeviceController,
        plan: StateActionPlan,
        expected_package: str,
        popup_feature: str,
    ) -> None:
        super().__init__(
            device=device,
            plan=plan,
            expected_package=expected_package,
            popup_feature=popup_feature,
        )
        if game_duration_seconds <= 0:
            raise ValueError("game_duration_seconds 必须 > 0")
        self._game_duration = game_duration_seconds
        self._exit_action = exit_action

    def advance(self, context: TaskContext) -> StepResult:
        if context.decision is not None and context.decision.state is PageState.GAME_RUNNING:
            started = context.get("game_started_at")
            if started is None:
                context.update_data(game_started_at=context.now)
                return StepResult(
                    "确认游戏运行，开始挂机计时",
                    actions=("GAME_TIMER_START",),
                    progress=True,
                )
            if context.now - float(started) >= self._game_duration:
                return self._execute(self._exit_action, context)
        return super().advance(context)


def build_game_definition(
    keys: FeatureKeys,
    observer: PageObserver,
    device: DeviceController,
    recovery: RecoveryStrategy,
    recognizer: PageStateRecognizer,
    *,
    timeout_seconds: float = DEFAULT_GAME_TIMEOUT_SECONDS,
    game_duration_seconds: float = DEFAULT_GAME_DURATION_SECONDS,
    captcha_guard: Optional[CaptchaGuard] = None,
) -> TaskDefinition:
    """装配游戏任务。"""
    adapter = GameTaskAdapter(
        game_duration_seconds=game_duration_seconds,
        exit_action=Action.tap_feature(keys.game_exit_menu),
        device=device,
        plan=build_game_action_plan(keys),
        expected_package=keys.qq_reader_package,
        popup_feature=keys.popup_close,
    )
    return TaskDefinition(
        contract=build_game_contract(keys, timeout_seconds=timeout_seconds),
        observer=observer,
        adapter=adapter,
        recovery=recovery,
        captcha_guard=captcha_guard or ManualCaptchaGuard(),
        state_recognizer=recognizer,
    )
