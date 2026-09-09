"""广告任务契约与适配器（AGENTS.md §3.4）。

流程：``QQ 阅读主页 → 自动寻找奖励入口 → 进入奖励页 → 确认加载完成 →
找到广告任务 → 观看 → 返回奖励页 → 判断次数/验证码 → 12/12 或明日再来``。

**不得**再把「已经位于奖励页」当作隐含前置条件；``start_condition`` 允许
主页或奖励页，``ready_condition`` 才要求奖励页确实就绪。
"""

from __future__ import annotations

from typing import Optional

from ..captcha.guard import CaptchaGuard, ManualCaptchaGuard
from ..contract.conditions import StateIs, all_of, any_of, feature, state_in
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

AD_TASK_NAME = "DailyAdFlow"
DEFAULT_AD_TIMEOUT_SECONDS = 45 * 60


def build_ad_contract(
    keys: FeatureKeys = DEFAULT_FEATURE_KEYS,
    *,
    timeout_seconds: float = DEFAULT_AD_TIMEOUT_SECONDS,
    timeout_label: str = "广告任务独立超时",
) -> TaskContract:
    """构造广告任务的 8 字段契约。"""
    return TaskContract(
        name=AD_TASK_NAME,
        description="奖励页视频广告：主页 → 奖励页 → 逐轮观看 → 12/12 或明日再来",
        start_condition=state_in(PageState.HOME, PageState.REWARD_HOME),
        ready_condition=all_of(
            StateIs(PageState.REWARD_HOME),
            any_of(
                feature(ocr(keys.reward_ocr_watch)),
                feature(ocr(keys.reward_ocr_ad_banner)),
            ),
        ),
        progress_condition=state_in(
            PageState.AD_PLAYING, PageState.AD_RESULT, PageState.REWARD_HOME
        ),
        captcha_condition=captcha_condition(keys),
        success_condition=any_of(
            feature(ocr(keys.ad_success_counter)),
            feature(ocr(keys.ad_success_regex, mode=MatchMode.REGEX)),
        ),
        recoverable_error=(
            popup_recoverable(keys),
            wrong_page_recoverable(
                "wrong_page_ad",
                (PageState.GAME_LOADING, PageState.GAME_RUNNING, PageState.GAME_RESULT),
                "误入游戏页面，返回奖励页",
            ),
        ),
        fatal_error=health_fatal_errors(keys),
        timeout=TimeoutSpec(timeout_seconds, timeout_label),
    )


def build_ad_action_plan(keys: FeatureKeys = DEFAULT_FEATURE_KEYS) -> StateActionPlan:
    """广告任务的状态 → 动作计划。"""
    return StateActionPlan(
        actions={
            PageState.HOME: Action.tap_feature(
                feature_key(keys, keys.home_ocr_reward_entry)
            ),
            PageState.REWARD_HOME: Action.tap_feature(
                feature_key(keys, keys.reward_ocr_watch)
            ),
            PageState.AD_PLAYING: Action.wait(5.0),
            PageState.AD_RESULT: Action.tap_feature(
                feature_key(keys, keys.ad_result_close)
            ),
            # 误入游戏页面时先返回；真正的恢复由 recoverable_error 驱动。
            PageState.GAME_LOADING: Action.press_back(),
            PageState.GAME_RUNNING: Action.press_back(),
            PageState.GAME_RESULT: Action.press_back(),
        },
        unknown_action=Action.reobserve(),
        bootstrap_action=Action.launch_app(keys.qq_reader_package),
    )


class AdTaskAdapter(PlannedTaskAdapter):
    """广告任务适配器：奖励页滚动找视频入口，播放页处理跳过/继续/关闭。"""

    def __init__(
        self,
        *,
        device: DeviceController,
        plan: StateActionPlan,
        expected_package: str,
        popup_feature: Optional[str],
        watch_key: str = feature_key(
            DEFAULT_FEATURE_KEYS, DEFAULT_FEATURE_KEYS.reward_ocr_watch
        ),
        watch_alt_key: str = feature_key(
            DEFAULT_FEATURE_KEYS, DEFAULT_FEATURE_KEYS.reward_ocr_watch_alt
        ),
        watch_partial_key: str = feature_key(
            DEFAULT_FEATURE_KEYS, DEFAULT_FEATURE_KEYS.reward_ocr_watch_partial
        ),
        banner_key: str = feature_key(
            DEFAULT_FEATURE_KEYS, DEFAULT_FEATURE_KEYS.reward_ocr_ad_banner
        ),
        skip_key: str = feature_key(
            DEFAULT_FEATURE_KEYS, DEFAULT_FEATURE_KEYS.ad_ocr_skip
        ),
        continue_key: str = feature_key(
            DEFAULT_FEATURE_KEYS, DEFAULT_FEATURE_KEYS.ad_ocr_continue
        ),
        close_key: str = feature_key(
            DEFAULT_FEATURE_KEYS, DEFAULT_FEATURE_KEYS.ad_ocr_close
        ),
        claim_exit_key: str = feature_key(
            DEFAULT_FEATURE_KEYS, DEFAULT_FEATURE_KEYS.ad_ocr_claim_after_exit
        ),
        force_exit_key: str = feature_key(
            DEFAULT_FEATURE_KEYS, DEFAULT_FEATURE_KEYS.ad_ocr_force_exit
        ),
        watch_text: str = DEFAULT_FEATURE_KEYS.reward_ocr_watch,
        watch_alt_text: str = DEFAULT_FEATURE_KEYS.reward_ocr_watch_alt,
        banner_text: str = DEFAULT_FEATURE_KEYS.reward_ocr_ad_banner,
        skip_text: str = DEFAULT_FEATURE_KEYS.ad_ocr_skip,
        continue_text: str = DEFAULT_FEATURE_KEYS.ad_ocr_continue,
        close_text: str = DEFAULT_FEATURE_KEYS.ad_ocr_close,
        claim_exit_text: str = DEFAULT_FEATURE_KEYS.ad_ocr_claim_after_exit,
        force_exit_text: str = DEFAULT_FEATURE_KEYS.ad_ocr_force_exit,
        watch_partial_text: str = "立",
        watch_point_action: Optional[Action] = None,
        offer_texts: tuple = (
            DEFAULT_FEATURE_KEYS.ad_ocr_offer,
            DEFAULT_FEATURE_KEYS.ad_ocr_offer_alt,
        ),
        offer_close_action: Optional[Action] = None,
        initial_wait_seconds: float = 40.0,
        scroll_action: Optional[Action] = None,
        max_scrolls: int = 24,
    ) -> None:
        super().__init__(
            device=device,
            plan=plan,
            expected_package=expected_package,
            popup_feature=popup_feature,
        )
        self._watch_key = watch_key
        self._watch_alt_key = watch_alt_key
        self._watch_partial_key = watch_partial_key
        self._banner_key = banner_key
        self._skip_key = skip_key
        self._continue_key = continue_key
        self._close_key = close_key
        self._claim_exit_key = claim_exit_key
        self._force_exit_key = force_exit_key
        self._watch_text = watch_text
        self._watch_alt_text = watch_alt_text
        self._banner_text = banner_text
        self._skip_text = skip_text
        self._continue_text = continue_text
        self._close_text = close_text
        self._claim_exit_text = claim_exit_text
        self._force_exit_text = force_exit_text
        self._watch_partial_text = watch_partial_text
        self._watch_point_action = watch_point_action or Action.tap_point(
            600, 1078
        )
        self._offer_texts = tuple(offer_texts)
        self._offer_close_action = offer_close_action or Action.press_back()
        self._initial_wait_seconds = float(initial_wait_seconds)
        self._scroll_action = scroll_action or Action.swipe(
            360, 1000, 360, 350, 500
        )
        self._max_scrolls = max_scrolls

    def advance(self, context: TaskContext) -> StepResult:
        state = context.decision.state if context.decision is not None else None
        if state is PageState.REWARD_HOME:
            has_banner = self._has_text(context, self._banner_text)
            if self._has_text(context, self._watch_text):
                return self._tap_feature_or_point(
                    context, self._watch_key, self._watch_point_action
                )
            if self._has_text(context, self._watch_alt_text):
                return self._tap_feature_or_point(
                    context, self._watch_alt_key, self._watch_point_action
                )
            if has_banner and self._has_text(context, self._watch_partial_text):
                return self._tap_feature_or_point(
                    context,
                    self._watch_partial_key,
                    self._watch_point_action,
                )
            if has_banner:
                return self._execute(
                    Action.tap_feature(self._banner_key), context
                )
            attempts = int(context.get("ad_entry_scrolls", 0))
            if attempts < self._max_scrolls:
                context.update_data(ad_entry_scrolls=attempts + 1)
                return self._execute(self._scroll_action, context)
        elif state is PageState.AD_PLAYING:
            if not context.get("ad_initial_wait_done"):
                context.update_data(ad_initial_wait_done=True)
                return self._execute(
                    Action.wait(self._initial_wait_seconds), context
                )
            if self._has_text(context, self._claim_exit_text):
                return self._execute(
                    Action.tap_feature(self._claim_exit_key), context
                )
            if self._has_text(context, self._continue_text):
                return self._execute(
                    Action.tap_feature(self._continue_key), context
                )
            if self._has_text(context, self._force_exit_text):
                return self._execute(
                    Action.tap_feature(self._force_exit_key), context
                )
            if any(self._has_text(context, item) for item in self._offer_texts):
                return self._execute(self._offer_close_action, context)
            if self._has_text(context, self._skip_text):
                return self._execute(Action.tap_feature(self._skip_key), context)
            if self._has_text(context, self._close_text):
                return self._execute(Action.tap_feature(self._close_key), context)
            waits = int(context.get("ad_play_waits", 0))
            if waits >= 12:
                # 广告层不自动关闭时，持续按返回键逐层退出，直到回到奖励页。
                return self._execute(Action.press_back(), context)
            if waits == 6:
                context.update_data(ad_play_waits=waits + 1)
                # 直播/浏览广告倒计时结束后不自动关闭，尝试左上角 X。
                return self._execute(Action.tap_point(55, 118), context)
            context.update_data(ad_play_waits=waits + 1)
            return self._execute(Action.wait(5.0), context)
        elif state is PageState.AD_RESULT:
            if self._has_text(context, self._close_text):
                return self._execute(Action.tap_feature(self._close_key), context)
        return super().advance(context)

    def _tap_feature_or_point(
        self,
        context: TaskContext,
        feature_key: str,
        fallback: Action,
    ) -> StepResult:
        step = self._execute(Action.tap_feature(feature_key), context)
        if not step.progress:
            return self._execute(fallback, context)
        return step

    @staticmethod
    def _has_text(context: TaskContext, needle: str) -> bool:
        return any(needle in text for text in context.observation.ocr_texts)



def build_ad_definition(
    keys: FeatureKeys,
    observer: PageObserver,
    device: DeviceController,
    recovery: RecoveryStrategy,
    recognizer: PageStateRecognizer,
    *,
    timeout_seconds: float = DEFAULT_AD_TIMEOUT_SECONDS,
    captcha_guard: Optional[CaptchaGuard] = None,
) -> TaskDefinition:
    """装配广告任务（契约 + 观测器 + 适配器 + 恢复 + 验证码守卫）。"""
    adapter = AdTaskAdapter(
        device=device,
        plan=build_ad_action_plan(keys),
        expected_package=keys.qq_reader_package,
        popup_feature=feature_key(keys, keys.popup_close),
        watch_key=feature_key(keys, keys.reward_ocr_watch),
        watch_alt_key=feature_key(keys, keys.reward_ocr_watch_alt),
        watch_partial_key=feature_key(keys, keys.reward_ocr_watch_partial),
        banner_key=feature_key(keys, keys.reward_ocr_ad_banner),
        skip_key=feature_key(keys, keys.ad_ocr_skip),
        continue_key=feature_key(keys, keys.ad_ocr_continue),
        close_key=feature_key(keys, keys.ad_ocr_close),
        claim_exit_key=feature_key(keys, keys.ad_ocr_claim_after_exit),
        force_exit_key=feature_key(keys, keys.ad_ocr_force_exit),
        watch_text=keys.reward_ocr_watch,
        watch_alt_text=keys.reward_ocr_watch_alt,
        banner_text=keys.reward_ocr_ad_banner,
        skip_text=keys.ad_ocr_skip,
        continue_text=keys.ad_ocr_continue,
        close_text=keys.ad_ocr_close,
        claim_exit_text=keys.ad_ocr_claim_after_exit,
        force_exit_text=keys.ad_ocr_force_exit,
    )
    return TaskDefinition(
        contract=build_ad_contract(keys, timeout_seconds=timeout_seconds),
        observer=observer,
        adapter=adapter,
        recovery=recovery,
        captcha_guard=captcha_guard or ManualCaptchaGuard(),
        state_recognizer=recognizer,
    )
