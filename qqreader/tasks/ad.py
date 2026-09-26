"""广告任务契约与适配器（AGENTS.md §3.4）。

流程：``QQ 阅读主页 → 自动寻找奖励入口 → 进入奖励页 → 确认加载完成 →
找到广告任务 → 观看 → 返回奖励页 → 判断次数/验证码 → 12/12 或明日再来``。

**不得**再把「已经位于奖励页」当作隐含前置条件；``start_condition`` 允许
主页或奖励页，``ready_condition`` 才要求奖励页确实就绪。
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Optional

from ..captcha.factory import build_default_captcha_guard
from ..captcha.guard import CaptchaGuard, ManualCaptchaGuard
from ..contract.conditions import (
    ConditionResult,
    StateIs,
    all_of,
    any_of,
    callable_condition,
    feature,
    state_in,
)
from ..contract.contract import FatalErrorSpec, TaskContract, TimeoutSpec
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
from .plan import Action, ActionKind, PlannedTaskAdapter, StateActionPlan

if TYPE_CHECKING:  # pragma: no cover
    from ..maa.client import MaaClient

AD_TASK_NAME = "DailyAdFlow"
DEFAULT_AD_TIMEOUT_SECONDS = 45 * 60


def _image_corner_x(png: bytes) -> Optional[tuple[int, int]]:
    """在顶部两角找圆圈 X；双对角线可排除相邻的静音圆钮。"""
    try:
        import cv2  # type: ignore[import-not-found]
        import numpy as np  # type: ignore[import-not-found]
    except ImportError:
        return None
    image = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None or image.shape[0] < 160 or image.shape[1] < 260:
        return None
    top = image[:160]
    candidates: list[tuple[float, int, int]] = []
    for start in (0, image.shape[1] - 130):
        circles = cv2.HoughCircles(
            top[:, start:start + 130], cv2.HOUGH_GRADIENT,
            dp=1.2, minDist=26, param1=100, param2=15,
            minRadius=12, maxRadius=28,
        )
        if circles is None:
            continue
        for local_x, local_y, _ in circles[0]:
            center_x, center_y = int(round(local_x + start)), int(round(local_y))
            # Hough 圆心有 1–2px 偏差；X 的细线只在真实圆心上同时命中。
            for x in range(center_x - 2, center_x + 3):
                for y in range(center_y - 2, center_y + 3):
                    if not (45 <= y <= 140 and 25 <= x < image.shape[1] - 25):
                        continue
                    offsets = np.arange(3, 10)
                    diagonal_a = np.r_[top[y + offsets, x + offsets],
                                       top[y - offsets, x - offsets]].mean()
                    diagonal_b = np.r_[top[y + offsets, x - offsets],
                                       top[y - offsets, x + offsets]].mean()
                    axes = np.r_[top[y, x + offsets], top[y, x - offsets],
                                 top[y + offsets, x], top[y - offsets, x]].mean()
                    a, b = float(diagonal_a - axes), float(diagonal_b - axes)
                    if min(a, b) >= 45 or max(a, b) <= -45:
                        candidates.append((min(abs(a), abs(b)), x, y))
    if not candidates:
        return None
    _, x, y = max(candidates)
    return x, y


def _locate_visible_corner_close(client: "MaaClient") -> Optional[Action]:
    """取最新实机帧，定位广告的左上或右上关闭按钮。"""
    shot = client.screencap()
    result = client.recognize("OCR", {}, shot)
    texts = result.all_texts()
    if any(
        marker in text for text in texts
        for marker in ("安全验证", "拖动下方滑块", "完成拼图")
    ):
        return Action.wait(1.0)
    point = _image_corner_x(shot.data)
    if point is not None:
        return Action.tap_point(*point)
    for text, (x, y, width, height) in result.text_boxes():
        cx, cy = x + width // 2, y + height // 2
        if (text.strip().casefold() in {"x", "×"}
                and 25 <= cy <= 150
                and (cx <= 120 or cx >= shot.width - 120)):
            return Action.tap_point(cx, cy)
    return None


def _watch_entry_error(context: TaskContext) -> ConditionResult:
    message = context.get("ad_watch_entry_error")
    error_state = context.get("ad_watch_entry_error_state")
    current_state = context.state.value if context.state is not None else None
    if message and error_state == current_state:
        return ConditionResult.yes(str(message))
    if message:
        return ConditionResult.no(
            f"广告入口错误属于旧页面 {error_state}，当前已切换到 {current_state}"
        )
    return ConditionResult.no("奖励页入口滚动查找尚未报错")


def _exit_unconfirmed(context: TaskContext) -> ConditionResult:
    message = context.get("ad_exit_error")
    if message and context.state in (PageState.AD_PLAYING, PageState.AD_RESULT):
        return ConditionResult.yes(str(message))
    return ConditionResult.no("广告退出仍在等待页面确认")


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
        start_condition=state_in(PageState.HOME, PageState.REWARD_HOME, PageState.GAME_ENTRY),
        ready_condition=any_of(
            state_in(PageState.AD_PLAYING, PageState.AD_RESULT),
            all_of(
                state_in(PageState.REWARD_HOME, PageState.GAME_ENTRY),
                any_of(
                    feature(ocr(keys.reward_ocr_watch)),
                    feature(ocr(keys.reward_ocr_ad_banner)),
                ),
            ),
        ),
        progress_condition=state_in(
            PageState.AD_PLAYING, PageState.AD_RESULT, PageState.REWARD_HOME,
            PageState.GAME_ENTRY,
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
        fatal_error=health_fatal_errors(keys)
        + (
            FatalErrorSpec(
                "ad_watch_entry_not_found",
                callable_condition(_watch_entry_error, "广告入口滚动查找失败"),
                "首屏及最多 8 次下滑均未找到立即观看入口",
            ),
            FatalErrorSpec(
                "ad_exit_unconfirmed",
                callable_condition(_exit_unconfirmed, "广告退出未得到页面确认"),
                "退出广告后仍停留广告页；停止再次退出并保留现场",
            ),
        ),
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
        navigation_client: Optional["MaaClient"] = None,
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
        abandon_reward_key: str = feature_key(
            DEFAULT_FEATURE_KEYS, DEFAULT_FEATURE_KEYS.ad_ocr_abandon_reward
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
        accelerate_key: str = feature_key(
            DEFAULT_FEATURE_KEYS, DEFAULT_FEATURE_KEYS.ad_ocr_accelerate
        ),
        completed_key: str = feature_key(
            DEFAULT_FEATURE_KEYS, DEFAULT_FEATURE_KEYS.ad_ocr_completed
        ),
        watch_text: str = DEFAULT_FEATURE_KEYS.reward_ocr_watch,
        watch_alt_text: str = DEFAULT_FEATURE_KEYS.reward_ocr_watch_alt,
        banner_text: str = DEFAULT_FEATURE_KEYS.reward_ocr_ad_banner,
        skip_text: str = DEFAULT_FEATURE_KEYS.ad_ocr_skip,
        continue_text: str = DEFAULT_FEATURE_KEYS.ad_ocr_continue,
        abandon_reward_text: str = DEFAULT_FEATURE_KEYS.ad_ocr_abandon_reward,
        close_text: str = DEFAULT_FEATURE_KEYS.ad_ocr_close,
        claim_exit_text: str = DEFAULT_FEATURE_KEYS.ad_ocr_claim_after_exit,
        force_exit_text: str = DEFAULT_FEATURE_KEYS.ad_ocr_force_exit,
        accelerate_text: str = DEFAULT_FEATURE_KEYS.ad_ocr_accelerate,
        completed_text: str = DEFAULT_FEATURE_KEYS.ad_ocr_completed,
        watch_partial_text: str = "立",
        watch_point_action: Optional[Action] = None,
        offer_close_action: Optional[Action] = None,
        completed_close_action: Optional[Action] = None,
        initial_wait_seconds: float = 35.0,
        live_texts: tuple = (
            "进入直播间",
            "直播中",
            "需要下滑",
            "上滑或点击",
            "扭一扭或点击",
            "下滑",
            "去体验",
        ),
        live_scroll_wait_seconds: float = 5.0,
        max_live_scroll_swipes: int = 8,
        live_exit_action: Optional[Action] = None,
        scroll_action: Optional[Action] = None,
        max_scrolls: int = 8,
        entry_settle_seconds: float = 1.0,
        entry_transition_seconds: float = 8.0,
    ) -> None:
        super().__init__(
            device=device,
            plan=plan,
            expected_package=expected_package,
            popup_feature=popup_feature,
        )
        self._watch_key = watch_key
        self._navigation_client = navigation_client
        self._watch_alt_key = watch_alt_key
        self._watch_partial_key = watch_partial_key
        self._banner_key = banner_key
        self._skip_key = skip_key
        self._continue_key = continue_key
        self._abandon_reward_key = abandon_reward_key
        self._close_key = close_key
        self._claim_exit_key = claim_exit_key
        self._force_exit_key = force_exit_key
        self._accelerate_key = accelerate_key
        self._completed_key = completed_key
        self._watch_text = watch_text
        self._watch_alt_text = watch_alt_text
        self._banner_text = banner_text
        self._skip_text = skip_text
        self._continue_text = continue_text
        self._abandon_reward_text = abandon_reward_text
        self._close_text = close_text
        self._claim_exit_text = claim_exit_text
        self._force_exit_text = force_exit_text
        self._accelerate_texts = tuple(
            part for part in accelerate_text.split("|") if part
        )
        self._completed_texts = tuple(
            part for part in completed_text.split("|") if part
        )
        self._watch_partial_text = watch_partial_text
        self._watch_point_action = watch_point_action or Action.tap_point(
            600, 1078
        )
        self._offer_close_action = offer_close_action or Action.tap_point(48, 70)
        self._completed_close_action = completed_close_action or Action.tap_point(
            48, 70
        )
        self._initial_wait_seconds = float(initial_wait_seconds)
        self._live_texts = tuple(live_texts)
        self._live_scroll_wait_seconds = float(live_scroll_wait_seconds)
        self._max_live_scroll_swipes = int(max_live_scroll_swipes)
        self._live_exit_action = live_exit_action or Action.tap_point(48, 70)
        self._scroll_action = scroll_action or Action.swipe(
            360, 1000, 360, 350, 500
        )
        self._max_scrolls = max_scrolls
        self._entry_settle_seconds = float(entry_settle_seconds)
        self._entry_transition_seconds = float(entry_transition_seconds)

    def advance(self, context: TaskContext) -> StepResult:
        state = context.decision.state if context.decision is not None else None
        settle = float(context.get("ad_exit_settle_until", 0)) - context.now
        if settle > 0:
            # Close is asynchronous: a fresh screenshot can still contain the
            # outgoing ad. Never queue Back while that close is in flight.
            return self._execute(Action.wait(settle), context)
        exit_sent_at = context.get("ad_exit_sent_at")
        if exit_sent_at is not None:
            if state in (PageState.REWARD_HOME, PageState.GAME_ENTRY, PageState.HOME):
                context.data.pop("ad_exit_sent_at", None)
                context.data.pop("ad_exit_error", None)
                context.data.pop("ad_rating_close_sent", None)
                context.data.pop("ad_exit_fallbacks", None)
            elif state in (PageState.AD_PLAYING, PageState.AD_RESULT):
                if self._is_rating_modal(context) and not context.get("ad_rating_close_sent"):
                    context.update_data(ad_rating_close_sent=True)
                    return self._execute(
                        self._visible_corner_close(context) or Action.tap_point(53, 112),
                        context,
                    )
                # X 后可能仍显示离场中的广告。只在明确出现退出确认按钮时
                # 允许下一次点击；不能因为同一广告帧还在就紧接着按 Back。
                has_exit_modal = any(
                    self._has_text(context, label)
                    for label in ("放弃奖励", "坚持退出")
                )
                if not has_exit_modal:
                    if context.now - float(exit_sent_at) < 20.0:
                        return self._execute(Action.wait(2.0), context)
                    # 2026-09-23 实测：部分广告（奖励已发放的「了解详情」卡、
                    # 评分弹窗）不响应返回键，只能点左上角 X。第一次退出动作
                    # 20 秒没生效时，先换一种退出方式再判失败，而不是直接放弃。
                    fallbacks = int(context.get("ad_exit_fallbacks", 0))
                    fallback_actions = (
                        self._visible_corner_close(context)
                        or (Action.tap_point(53, 112)
                            if self._is_rating_modal(context)
                            else self._completed_close_action),
                        Action.press_back(),
                    )
                    if fallbacks < len(fallback_actions):
                        context.update_data(ad_exit_fallbacks=fallbacks + 1)
                        context.data.pop("ad_exit_sent_at", None)
                        return self._execute(fallback_actions[fallbacks], context)
                    context.update_data(ad_exit_error="关闭广告后 20 秒仍未确认返回奖励页")
                    return StepResult.noop("广告退出未确认；停止重复返回，保留当前页面")
                context.data.pop("ad_exit_sent_at", None)
        entry_transition = float(
            context.get("ad_entry_transition_until", 0)
        ) - context.now
        if entry_transition > 0 and state in (
            PageState.REWARD_HOME,
            PageState.GAME_ENTRY,
        ):
            # QQ 阅读有时会在入口点击后继续显示奖励页数秒，再异步拉起
            # 广告。等待这次页面转换完成，不能把仍在离场的奖励页当成
            # “下一轮”并立即滚动八屏，否则会在广告落地页上误报入口缺失。
            return self._execute(Action.wait(entry_transition), context)
        if state not in (PageState.REWARD_HOME, PageState.GAME_ENTRY):
            context.data.pop("ad_entry_transition_until", None)
            context.update_data(ad_entry_no_transition_rounds=0)
        # UNKNOWN 兜底：连续 6 次未识别（游戏中心等异常页）时按返回键
        # 逐层退出，直到回到 HOME/书架可识别页。
        if state in (None, PageState.GAME_CENTER, PageState.GAME_HALL):
            unknowns = int(context.get("ad_unknown_backs", 0))
            if unknowns >= 6 and unknowns < 14:
                context.update_data(ad_unknown_backs=unknowns + 1)
                return self._execute(Action.press_back(), context)
            context.update_data(ad_unknown_backs=unknowns + 1)
        else:
            context.update_data(ad_unknown_backs=0)
        # 书城 tab 上没有奖励入口（home_ocr_reward_entry 在书架 tab）。
        # HOME 状态下找不到入口文案时先点底部「书架」tab（issue: 书城页空转）。
        if state is PageState.HOME:
            if self._navigation_client is not None:
                # HOME 的奖励入口文案会随版本/账号变化（例如“本周阅读时长”
                # 变成“554分钟 / 时长兑赠币，立即领取”）。复用统一导航器，
                # 让它依据当前 OCR 点击实际入口并逐帧确认已进入奖励页。
                from ..reward.nav import goto_reward_page

                if goto_reward_page(
                    self._navigation_client,
                    settle_seconds=self._entry_settle_seconds,
                    sleep=lambda seconds: context.clock.sleep(seconds, context.token),
                ):
                    context.data.pop("ad_watch_entry_error", None)
                    context.data.pop("ad_watch_entry_error_state", None)
                    return StepResult(
                        "从首页定位奖励入口并确认进入奖励页",
                        actions=(ActionKind.TAP_POINT.value,),
                        progress=True,
                    )
                message = "无法从首页定位奖励入口并确认进入奖励页"
                context.update_data(
                    ad_watch_entry_error=message,
                    ad_watch_entry_error_state=PageState.HOME.value,
                )
                return StepResult(
                    message,
                    actions=(ActionKind.REOBSERVE.value,),
                    progress=False,
                )
            has_entry = any(
                needle in text
                for text in context.observation.ocr_texts
                for needle in ("本周阅读时长", "分钟领")
            )
            taps = int(context.get("ad_shelf_tab_taps", 0))
            if not has_entry and taps < 3:
                context.update_data(ad_shelf_tab_taps=taps + 1)
                return self._execute(Action.tap_point(89, 1263), context)
        # GAME_ENTRY is the same reward page when its game row is visible.
        if state in (PageState.REWARD_HOME, PageState.GAME_ENTRY):
            # 实机可能在广告库存/页面状态异常时吞掉“立即观看”点击，按钮仍在、
            # 页面也完全不跳转。不能无限重复点击到超时；连续三次转换窗口结束
            # 后仍停在奖励页，就先返回书架，再由 HOME 导航链重新进入奖励页。
            if context.get("ad_entry_transition_until"):
                ignored = int(context.get("ad_entry_no_transition_rounds", 0)) + 1
                context.data.pop("ad_entry_transition_until", None)
                context.update_data(ad_entry_no_transition_rounds=ignored)
                if ignored >= 3:
                    context.update_data(ad_entry_no_transition_rounds=0)
                    return self._execute(Action.press_back(), context)
            context.update_data(
                ad_initial_wait_done=False, ad_play_waits=0,
                ad_scroll_phase="wait", ad_scroll_swipes=0,
                ad_live_exit_pending=False,
                ad_offerwall_exit_rounds=0,
                ad_offerwall_countdown_seen=False,
                ad_rating_close_sent=False,
            )
            if self._navigation_client is not None:
                # 延迟导入避免 reward.nav → maa.__init__ → factory → tasks
                # 在模块初始化阶段形成循环依赖。
                from ..reward.nav import find_watch_entry

                entry = find_watch_entry(
                    self._navigation_client,
                    max_scrolls=self._max_scrolls,
                    settle_seconds=self._entry_settle_seconds,
                    sleep=lambda seconds: context.clock.sleep(seconds, context.token),
                )
                if entry is None:
                    message = (
                        "奖励页广告入口查找失败：首屏及最多 "
                        f"{self._max_scrolls} 次下滑均未找到“立即观看”"
                    )
                    context.update_data(
                        ad_watch_entry_error=message,
                        ad_watch_entry_error_state=state.value,
                    )
                    return StepResult(
                        message,
                        actions=(ActionKind.REOBSERVE.value,),
                        progress=False,
                    )
                text, (x, y, width, height) = entry
                if not self._navigation_client.click(
                    x + width // 2, y + height // 2
                ):
                    message = f"已定位“{text}”，但点击广告入口失败"
                    context.update_data(
                        ad_watch_entry_error=message,
                        ad_watch_entry_error_state=state.value,
                    )
                    return StepResult(message, progress=False)
                context.update_data(
                    ad_entry_transition_until=(
                        context.now + self._entry_transition_seconds
                    )
                )
                context.data.pop("ad_watch_entry_error", None)
                context.data.pop("ad_watch_entry_error_state", None)
                return StepResult(
                    f"滚动定位并点击广告入口“{text}”",
                    actions=(ActionKind.TAP_POINT.value,),
                    progress=True,
                )
            has_banner = self._has_text(context, self._banner_text)
            # 必须先确认当前屏有广告卡，才允许点「立即观看」；否则只滚动，
            # 避免把其他页面残留的 OCR 文案当成广告按钮误点。
            if has_banner:
                if self._has_text(context, self._watch_text):
                    return self._tap_feature_or_point(
                        context, self._watch_key, self._watch_point_action
                    )
                if self._has_text(context, self._watch_alt_text):
                    return self._tap_feature_or_point(
                        context, self._watch_alt_key, self._watch_point_action
                    )
                if self._has_text(context, self._watch_partial_text):
                    # The floating lottery covers the watch button. A lone
                    # 「立」also matches「立即分享」; move the card and reobserve.
                    return self._execute(self._scroll_action, context)
            attempts = int(context.get("ad_entry_scrolls", 0))
            if attempts < self._max_scrolls:
                context.update_data(ad_entry_scrolls=attempts + 1)
                return self._execute(self._scroll_action, context)
        elif state is PageState.AD_PLAYING:
            is_live = any(
                self._has_text(context, item) for item in self._live_texts
            )
            is_offerwall = self._is_offerwall(context)
            if is_offerwall or self._has_text(context, self._abandon_reward_text):
                return self._handle_offerwall(context)
            if not is_live and not context.get("ad_initial_wait_done"):
                context.update_data(ad_initial_wait_done=True)
                return self._execute(
                    Action.wait(self._initial_wait_seconds), context
                )
            if self._has_text(context, self._claim_exit_text):
                return self._execute(
                    Action.tap_feature(self._claim_exit_key), context
                )
            if any(
                self._has_text(context, item) for item in self._completed_texts
            ):
                return self._execute(
                    self._visible_corner_close(context) or self._completed_close_action,
                    context,
                )
            if any(
                self._has_text(context, item) for item in self._accelerate_texts
            ):
                return self._execute(
                    Action.tap_feature(self._accelerate_key), context
                )
            if self._has_text(context, self._continue_text):
                if is_live:
                    context.update_data(
                        ad_scroll_phase="wait", ad_scroll_swipes=0,
                        ad_live_exit_pending=False,
                    )
                return self._execute(
                    Action.tap_feature(self._continue_key), context
                )
            if self._has_text(context, self._force_exit_text):
                return self._execute(
                    Action.tap_feature(self._force_exit_key), context
                )
            # 广告完成倒计时后，关闭图标可能只有圆圈 X，没有“关闭”文字。
            # 从新截图定位左右上角的 X；右上角静音图标不能误当关闭。
            if not is_live:
                close = self._visible_corner_close(context)
                if close is not None:
                    return self._execute(close, context)
            # 「去体验N秒」浏览型广告：无 X、页面不滚动，「跳过」在顶部提示行。
            # 必须先点跳过；live 下滑处理对它无效（页面内容固定）。
            if self._has_text(context, "去体验"):
                # 浏览型拉活广告：跳过会弹「确定要退出吗」，两个按钮语义：
                # 去领取奖励=跳第三方体验后再领（无法自动化）；坚持退出=放弃。
                # 策略：先点跳过；弹窗若已有「坚持退出」则点它；否则 BACK 兜底。
                if self._has_text(context, "坚持退出"):
                    tries = int(context.get("browse_exit_tries", 0))
                    context.update_data(browse_exit_tries=tries + 1)
                    return self._execute(Action.tap_feature(self._force_exit_key), context)
                if self._has_text(context, "确定要退出吗"):
                    waits = int(context.get("ad_play_waits", 0))
                    context.update_data(ad_play_waits=waits + 1)
                    if waits >= 6:
                        return self._execute(Action.press_back(), context)
                    return self._execute(Action.wait(2.0), context)
                return self._execute(Action.tap_point(684, 24), context)
            # Modal buttons remain actionable even when the live ad is visible
            # behind the overlay. Reobserve after each action before scrolling.
            if is_live:
                return self._handle_live_ad(context)
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
                return self._execute(self._completed_close_action, context)
            context.update_data(ad_play_waits=waits + 1)
            return self._execute(Action.wait(5.0), context)
        elif state is PageState.AD_RESULT:
            if self._has_text(context, self._close_text):
                return self._execute(Action.tap_feature(self._close_key), context)
        return super().advance(context)

    def _execute(self, action: Action, context: TaskContext) -> StepResult:
        step = super()._execute(action, context)
        if step.progress and context.state in (PageState.AD_PLAYING, PageState.AD_RESULT):
            is_exit = action.kind in (ActionKind.PRESS_BACK, ActionKind.TAP_POINT)
            is_exit = is_exit or (
                action.kind is ActionKind.TAP_FEATURE
                and action.target in (self._close_key, self._claim_exit_key,
                                      self._force_exit_key, self._skip_key,
                                      self._abandon_reward_key)
            )
            if is_exit:
                context.update_data(
                    ad_exit_settle_until=context.now + 3.0,
                    ad_exit_sent_at=context.now,
                )
        return step

    def _handle_live_ad(self, context: TaskContext) -> StepResult:
        """直播间/浏览类广告：每 5 秒下滑一次，达到最大次数后退出。"""
        phase = context.get("ad_scroll_phase", "wait")
        swipes = int(context.get("ad_scroll_swipes", 0))
        if swipes >= self._max_live_scroll_swipes:
            if context.get("ad_live_exit_pending"):
                return StepResult.noop("直播广告已发送关闭，等待页面确认")
            context.update_data(ad_live_exit_pending=True)
            return self._execute(
                self._visible_corner_close(context) or self._live_exit_action,
                context,
            )
        if phase == "wait":
            context.update_data(ad_scroll_phase="swipe")
            return self._execute(
                Action.wait(self._live_scroll_wait_seconds), context
            )
        context.update_data(ad_scroll_phase="wait", ad_scroll_swipes=swipes + 1)
        return self._execute(self._scroll_action, context)

    def _handle_offerwall(self, context: TaskContext) -> StepResult:
        """每轮默认观看 35 秒，再关闭并等待返回确认。"""
        # Logo 遮挡时 OCR 会漏掉倒计时，观看时长不能依赖该文案。
        if not context.get("ad_initial_wait_done"):
            context.update_data(ad_initial_wait_done=True)
            return self._execute(Action.wait(self._initial_wait_seconds), context)
        if self._is_rating_modal(context) and not context.get("ad_rating_close_sent"):
            context.update_data(ad_rating_close_sent=True)
            return self._execute(
                self._visible_corner_close(context) or Action.tap_point(53, 112),
                context,
            )
        if self._has_text(context, self._abandon_reward_text):
            context.update_data(ad_offerwall_exit_rounds=0)
            return self._execute(
                Action.tap_feature(self._abandon_reward_key), context
            )

        if any(self._has_text(context, item) for item in self._completed_texts):
            # 「恭喜获得奖励」已出现：奖励已到手，这类卡片不响应返回键，
            # 直接点左上角 X（2026-09-23 实测返回键无效导致 ad_exit_unconfirmed）。
            return self._execute(
                self._visible_corner_close(context) or self._completed_close_action,
                context,
            )

        close = self._visible_corner_close(context)
        if close is not None:
            return self._execute(close, context)

        rounds = int(context.get("ad_offerwall_exit_rounds", 0))
        if rounds >= 3:
            context.update_data(ad_offerwall_exit_rounds=0)
            return self._execute(Action.restart_app(self._expected_package), context)

        context.update_data(ad_offerwall_exit_rounds=rounds + 1)
        if self._has_offerwall_close_mark(context):
            return self._execute(self._offer_close_action, context)
        return self._execute(Action.press_back(), context)

    def _visible_corner_close(self, context: TaskContext) -> Optional[Action]:
        """在广告页的新截图中定位顶部 X，避免误点右上角静音按钮。"""
        if self._navigation_client is None:
            return None
        return _locate_visible_corner_close(self._navigation_client)

    @staticmethod
    def _is_offerwall(context: TaskContext) -> bool:
        text = "".join(context.observation.ocr_texts)
        has_reward_countdown = re.search(
            r"观看.{0,4}秒.{0,6}奖励", text
        ) is not None
        # 同一个第三方拉活广告在倒计时结束后会移除“观看 N 秒”文案，
        # 但仍保留“跳转详情页或第三方应用 / 了解详情”。此时仍应沿用
        # 同一广告分支，避免重复开始观看计时。
        return "跳转详情页" in text and (
            has_reward_countdown or "了解详情" in text
        )

    @staticmethod
    def _has_offerwall_close_mark(context: TaskContext) -> bool:
        return any(
            text.strip().casefold() in {"x", "×"}
            for text in context.observation.ocr_texts
        )

    @staticmethod
    def _is_rating_modal(context: TaskContext) -> bool:
        texts = context.observation.ocr_texts
        return any(text.strip() == "5.0" for text in texts) and any(
            "了解详情" in text for text in texts
        )

    @staticmethod
    def _remaining_seconds(context: TaskContext) -> Optional[int]:
        for text in context.observation.ocr_texts:
            match = re.search(r"(\d+)\s*(?:秒|s)", text)
            if match:
                return int(match.group(1))
        return None

    def _tap_feature_or_point(
        self,
        context: TaskContext,
        feature_key: str,
        fallback: Action,
    ) -> StepResult:
        step = self._execute(Action.tap_feature(feature_key), context)
        # OCR text alone cannot validate a fixed screen coordinate after scroll.
        # A localization miss must not turn into an unrelated click.
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
    navigation_client: Optional["MaaClient"] = None,
) -> TaskDefinition:
    """装配广告任务（契约 + 观测器 + 适配器 + 恢复 + 验证码守卫）。"""
    contract = build_ad_contract(keys, timeout_seconds=timeout_seconds)
    adapter = AdTaskAdapter(
        device=device,
        plan=build_ad_action_plan(keys),
        expected_package=keys.qq_reader_package,
        popup_feature=feature_key(keys, keys.popup_close),
        navigation_client=navigation_client,
        watch_key=feature_key(keys, keys.reward_ocr_watch),
        watch_alt_key=feature_key(keys, keys.reward_ocr_watch_alt),
        watch_partial_key=feature_key(keys, keys.reward_ocr_watch_partial),
        banner_key=feature_key(keys, keys.reward_ocr_ad_banner),
        skip_key=feature_key(keys, keys.ad_ocr_skip),
        continue_key=feature_key(keys, keys.ad_ocr_continue),
        abandon_reward_key=feature_key(keys, keys.ad_ocr_abandon_reward),
        close_key=feature_key(keys, keys.ad_ocr_close),
        claim_exit_key=feature_key(keys, keys.ad_ocr_claim_after_exit),
        force_exit_key=feature_key(keys, keys.ad_ocr_force_exit),
        accelerate_key=feature_key(keys, keys.ad_ocr_accelerate),
        completed_key=feature_key(keys, keys.ad_ocr_completed),
        watch_text=keys.reward_ocr_watch,
        watch_alt_text=keys.reward_ocr_watch_alt,
        banner_text=keys.reward_ocr_ad_banner,
        skip_text=keys.ad_ocr_skip,
        continue_text=keys.ad_ocr_continue,
        abandon_reward_text=keys.ad_ocr_abandon_reward,
        close_text=keys.ad_ocr_close,
        claim_exit_text=keys.ad_ocr_claim_after_exit,
        force_exit_text=keys.ad_ocr_force_exit,
        accelerate_text=keys.ad_ocr_accelerate,
        completed_text=keys.ad_ocr_completed,
    )
    if captcha_guard is None:
        captcha_guard = build_default_captcha_guard(
            observer=observer,
            device=device,
            recognizer=recognizer,
            captcha_condition=contract.captcha_condition,
        )
    return TaskDefinition(
        contract=contract,
        observer=observer,
        adapter=adapter,
        recovery=recovery,
        captcha_guard=captcha_guard,
        state_recognizer=recognizer,
    )
