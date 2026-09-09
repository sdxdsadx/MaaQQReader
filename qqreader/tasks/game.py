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
    feature_key,
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
        start_condition=state_in(
            PageState.HOME, PageState.REWARD_HOME, PageState.GAME_ENTRY
        ),
        ready_condition=state_in(
            PageState.GAME_ENTRY, PageState.GAME_LOADING, PageState.GAME_RUNNING
        ),
        progress_condition=state_in(
            PageState.GAME_ENTRY,
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
            # 公共起点：主页先进入奖励页，再在奖励页找游戏入口。
            PageState.HOME: Action.tap_feature(
                feature_key(keys, keys.home_reward_entry)
            ),
            # 奖励页直接点击「去玩游戏」按钮；若页面先出现「玩游戏领赠币」
            # 中间态，GameTaskAdapter 会先点游戏卡，再点按钮。
            PageState.REWARD_HOME: Action.tap_feature(
                feature_key(keys, keys.game_ocr_go_play)
            ),
            # 游戏卡点击后出现的「去玩游戏」按钮。
            PageState.GAME_ENTRY: Action.tap_feature(
                feature_key(keys, keys.game_ocr_go_play)
            ),
            PageState.GAME_LOADING: Action.tap_feature(
                feature_key(keys, keys.game_ocr_enter_alt)
            ),
            PageState.GAME_RUNNING: Action.wait(10.0),
            PageState.GAME_RESULT: Action.tap_feature(
                feature_key(keys, keys.game_ocr_exit)
            ),
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
        reward_entry_key: str = DEFAULT_FEATURE_KEYS.logical_name(
            DEFAULT_FEATURE_KEYS.game_ocr_reward_entry
        ),
        go_play_key: str = DEFAULT_FEATURE_KEYS.logical_name(
            DEFAULT_FEATURE_KEYS.game_ocr_go_play
        ),
        reward_entry_text: str = DEFAULT_FEATURE_KEYS.game_ocr_reward_entry,
        go_play_text: str = DEFAULT_FEATURE_KEYS.game_ocr_go_play,
        entry_scroll_action: Optional[Action] = None,
        max_entry_scrolls: int = 4,
    ) -> None:
        super().__init__(
            device=device,
            plan=plan,
            expected_package=expected_package,
            popup_feature=popup_feature,
        )
        if game_duration_seconds <= 0:
            raise ValueError("game_duration_seconds 必须 > 0")
        if max_entry_scrolls < 0:
            raise ValueError("max_entry_scrolls 必须 >= 0")
        self._game_duration = game_duration_seconds
        self._exit_action = exit_action
        self._reward_entry_key = reward_entry_key
        self._go_play_key = go_play_key
        self._reward_entry_text = reward_entry_text
        self._go_play_text = go_play_text
        self._entry_scroll_action = entry_scroll_action
        self._max_entry_scrolls = max_entry_scrolls

    def advance(self, context: TaskContext) -> StepResult:
        state = context.decision.state if context.decision is not None else None

        # QQR-17：奖励页可能出现两种布局：
        # 1. 直接看到「去玩游戏」按钮 → 点按钮；
        # 2. 只看到「玩游戏领赠币」游戏卡 → 先点游戏卡，进入 GAME_ENTRY 后再点按钮。
        # 两者都不在屏幕内时，先按旧 pipeline 的坐标滚动查找。
        if state is PageState.REWARD_HOME:
            if self._has_text(context, self._go_play_text):
                context.update_data(game_entry_scrolls=0)
                return self._execute(Action.tap_feature(self._go_play_key), context)
            if self._has_text(context, self._reward_entry_text):
                context.update_data(game_entry_scrolls=0)
                return self._execute(
                    Action.tap_feature(self._reward_entry_key), context
                )
            if self._entry_scroll_action is not None:
                attempts = int(context.get("game_entry_scrolls", 0))
                if attempts < self._max_entry_scrolls:
                    context.update_data(game_entry_scrolls=attempts + 1)
                    return self._execute(self._entry_scroll_action, context)
        elif state is PageState.GAME_ENTRY:
            return self._execute(Action.tap_feature(self._go_play_key), context)

        if state is PageState.GAME_RUNNING:
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

    @staticmethod
    def _has_text(context: TaskContext, needle: str) -> bool:
        return any(needle in text for text in context.observation.ocr_texts)


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
    entry_scroll_action: Optional[Action] = None,
) -> TaskDefinition:
    """装配游戏任务。"""
    if entry_scroll_action is None:
        # 旧 pipeline GameScrollToPlay 的坐标，作为配置化之前的滚动兜底；
        # 仅用于奖励页游戏入口不在当前屏时查找，不做任何点击。
        entry_scroll_action = Action.swipe(360, 980, 360, 420, 500)
    adapter = GameTaskAdapter(
        game_duration_seconds=game_duration_seconds,
        exit_action=Action.tap_feature(feature_key(keys, keys.game_exit_menu)),
        device=device,
        plan=build_game_action_plan(keys),
        expected_package=keys.qq_reader_package,
        popup_feature=feature_key(keys, keys.popup_close),
        reward_entry_key=feature_key(keys, keys.game_ocr_reward_entry),
        go_play_key=feature_key(keys, keys.game_ocr_go_play),
        reward_entry_text=keys.game_ocr_reward_entry,
        go_play_text=keys.game_ocr_go_play,
        entry_scroll_action=entry_scroll_action,
    )
    return TaskDefinition(
        contract=build_game_contract(keys, timeout_seconds=timeout_seconds),
        observer=observer,
        adapter=adapter,
        recovery=recovery,
        captcha_guard=captcha_guard or ManualCaptchaGuard(),
        state_recognizer=recognizer,
    )
