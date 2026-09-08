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
            PageState.HOME: Action.tap_feature(keys.home_reward_entry),
            PageState.REWARD_HOME: Action.tap_feature(keys.reward_ocr_watch),
            PageState.AD_PLAYING: Action.wait(5.0),
            PageState.AD_RESULT: Action.tap_feature(keys.ad_result_close),
            # 误入游戏页面时先返回；真正的恢复由 recoverable_error 驱动。
            PageState.GAME_LOADING: Action.press_back(),
            PageState.GAME_RUNNING: Action.press_back(),
            PageState.GAME_RESULT: Action.press_back(),
        },
        unknown_action=Action.reobserve(),
        bootstrap_action=Action.launch_app(keys.qq_reader_package),
    )


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
    adapter = PlannedTaskAdapter(
        device=device,
        plan=build_ad_action_plan(keys),
        expected_package=keys.qq_reader_package,
        popup_feature=keys.popup_close,
    )
    return TaskDefinition(
        contract=build_ad_contract(keys, timeout_seconds=timeout_seconds),
        observer=observer,
        adapter=adapter,
        recovery=recovery,
        captcha_guard=captcha_guard or ManualCaptchaGuard(),
        state_recognizer=recognizer,
    )
