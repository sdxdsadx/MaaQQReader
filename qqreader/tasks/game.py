"""游戏任务契约与适配器（AGENTS.md §3.5）。

流程：``进入游戏 → 确认游戏真正启动 → 确认横竖屏 → 挂机（默认 25 分钟）→
周期性检查状态 → 退出 → 返回奖励页确认完成``。
"""

from __future__ import annotations

from typing import Optional, Tuple

from ..captcha.factory import build_default_captcha_guard
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
DEFAULT_GAME_DURATION_SECONDS = 22 * 60


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
            PageState.HOME,
            PageState.REWARD_HOME,
            PageState.GAME_ENTRY,
            PageState.GAME_HALL,
            PageState.GAME_CENTER,
            PageState.GAME_LOADING,
            PageState.GAME_RUNNING,
        ),
        ready_condition=state_in(
            PageState.GAME_ENTRY,
            PageState.GAME_HALL,
            PageState.GAME_LOADING,
            PageState.GAME_RUNNING,
        ),
        progress_condition=state_in(
            PageState.GAME_ENTRY,
            PageState.GAME_HALL,
            PageState.GAME_LOADING,
            PageState.GAME_RUNNING,
            PageState.GAME_MENU,
            PageState.GAME_EXIT_CONFIRM,
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
                feature_key(keys, keys.home_ocr_reward_entry)
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
            # 游戏大厅：GameTaskAdapter 会先下划一次再点「在线玩」。
            PageState.GAME_HALL: Action.tap_point(360, 360),
            # 游戏中心：点击第一张游戏卡的「在线玩」按钮（坐标 fallback）。
            PageState.GAME_CENTER: Action.tap_point(100, 982),
            # 登录/协议页：GameTaskAdapter 会先勾选协议再点「进入游戏」。
            PageState.GAME_LOADING: Action.tap_feature(
                feature_key(keys, keys.game_ocr_enter)
            ),
            PageState.GAME_RUNNING: Action.wait(10.0),
            PageState.GAME_MENU: Action.tap_feature(
                feature_key(keys, keys.game_ocr_exit)
            ),
            PageState.GAME_EXIT_CONFIRM: Action.tap_feature(
                feature_key(keys, keys.game_ocr_close_game)
            ),
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

    #: 这些文案出现时，即使页面带「领币」也不算真正进入游戏运行态。
    _RUNNING_BLOCK_TEXTS = (
        "正在连接服务器",
        "正在进入游戏",
        "进入游戏",
        "我已详细阅读并同意",
        "用户协议",
        "同意",
        "拒绝",
        "点击选服",
        "踏入仙途",
        "开始游戏",
        "精选大作",
        "今日必玩推荐",
        "新游",
        "活动",
        "排行",
        "分类",
        "去玩游戏",
    )

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
        enter_game_key: str = DEFAULT_FEATURE_KEYS.logical_name(
            DEFAULT_FEATURE_KEYS.game_ocr_enter
        ),
        enter_game_alt_key: str = DEFAULT_FEATURE_KEYS.logical_name(
            DEFAULT_FEATURE_KEYS.game_ocr_enter_alt
        ),
        exit_menu_key: str = DEFAULT_FEATURE_KEYS.logical_name(
            DEFAULT_FEATURE_KEYS.game_ocr_exit
        ),
        close_game_key: str = DEFAULT_FEATURE_KEYS.logical_name(
            DEFAULT_FEATURE_KEYS.game_ocr_close_game
        ),
        claim_key: str = DEFAULT_FEATURE_KEYS.logical_name(
            DEFAULT_FEATURE_KEYS.game_ocr_claim
        ),
        online_play_key: str = DEFAULT_FEATURE_KEYS.logical_name(
            DEFAULT_FEATURE_KEYS.game_ocr_online_play
        ),
        agree_key: str = DEFAULT_FEATURE_KEYS.logical_name(
            DEFAULT_FEATURE_KEYS.game_ocr_agree
        ),
        login_game_key: str = DEFAULT_FEATURE_KEYS.logical_name(
            DEFAULT_FEATURE_KEYS.game_ocr_login_game
        ),
        agreement_text: str = DEFAULT_FEATURE_KEYS.game_ocr_agreement,
        claim_text: str = DEFAULT_FEATURE_KEYS.game_ocr_claim,
        agree_text: str = DEFAULT_FEATURE_KEYS.game_ocr_agree,
        online_play_text: str = DEFAULT_FEATURE_KEYS.game_ocr_online_play,
        login_game_text: str = DEFAULT_FEATURE_KEYS.game_ocr_login_game,
        carousel_action: Optional[Action] = None,
        hall_swipe_action: Optional[Action] = None,
        game_center_online_play_action: Optional[Action] = None,
        game_center_online_play_points: Optional[Tuple[Action, ...]] = None,
        agreement_action: Optional[Action] = None,
        agreement_action_alt: Optional[Action] = None,
        reward_game_button_action: Optional[Action] = None,
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
        self._enter_game_key = enter_game_key
        self._enter_game_alt_key = enter_game_alt_key
        self._exit_menu_key = exit_menu_key
        self._close_game_key = close_game_key
        self._claim_key = claim_key
        self._online_play_key = online_play_key
        self._agree_key = agree_key
        self._login_game_key = login_game_key
        self._agreement_text = agreement_text
        self._claim_text = claim_text
        self._agree_text = agree_text
        self._online_play_text = online_play_text
        self._login_game_text = login_game_text
        self._carousel_action = carousel_action or Action.tap_point(360, 360)
        # QQR-20：游戏大厅先下划一次，再识别「在线玩」。
        self._hall_swipe_action = (
            hall_swipe_action or Action.swipe(360, 420, 360, 980, 500)
        )
        default_game_center_points = (
            Action.tap_point(98, 981),
            Action.tap_point(254, 981),
            Action.tap_point(408, 980),
            Action.tap_point(564, 982),
        )
        if game_center_online_play_points:
            self._game_center_online_play_points = tuple(
                game_center_online_play_points
            )
        elif game_center_online_play_action is not None:
            self._game_center_online_play_points = (game_center_online_play_action,)
        else:
            self._game_center_online_play_points = default_game_center_points
        # 协议勾选框在不同游戏里高度略有差异，准备两个坐标依次尝试。
        self._agreement_actions = tuple(
            action
            for action in (
                agreement_action or Action.tap_point(157, 1032),
                agreement_action_alt or Action.tap_point(152, 1066),
            )
            if action is not None
        )
        # 奖励页「去玩游戏」按钮的坐标 fallback（OCR 定位失败时使用）。
        self._reward_game_button_action = (
            reward_game_button_action or Action.tap_point(592, 606)
        )
        # 奖励页游戏入口可能在屏幕下方；未显式配置时使用旧 pipeline
        # GameScrollToPlay 的坐标作为查找 fallback。
        self._entry_scroll_action = (
            entry_scroll_action or Action.swipe(360, 980, 360, 420, 500)
        )
        self._max_entry_scrolls = max_entry_scrolls

    def advance(self, context: TaskContext) -> StepResult:
        state = context.decision.state if context.decision is not None else None

        # QQR-18/20：退出流程一旦启动，后续只允许「退出/关闭/返回奖励页」，
        # 绝不能再被游戏大厅/游戏中心/登录页/运行页重新拉进游戏。
        if context.get("game_exit_done"):
            if state is PageState.GAME_MENU:
                return self._execute(Action.tap_feature(self._exit_menu_key), context)
            if state is PageState.GAME_EXIT_CONFIRM:
                return self._execute(Action.tap_feature(self._close_game_key), context)
            if state in (PageState.REWARD_HOME, PageState.GAME_ENTRY):
                if self._has_text(context, self._claim_text):
                    return self._execute(Action.tap_feature(self._claim_key), context)
                return StepResult(
                    "游戏已退出，奖励页暂未出现可领取按钮",
                    actions=(),
                    progress=False,
                )
            if state in (
                PageState.GAME_HALL,
                PageState.GAME_CENTER,
                PageState.GAME_LOADING,
                PageState.GAME_RUNNING,
                PageState.GAME_RESULT,
            ):
                return self._execute(Action.press_back(), context)

        # 游戏大厅：QQR-20 进入游戏后先下划一次，再识别「在线玩」点击进入游戏；
        # 退出游戏后按返回键回奖励页，不再下划/点击。
        if state is PageState.GAME_HALL:
            if context.get("game_exit_done"):
                return self._execute(Action.press_back(), context)
            if not context.get("game_hall_swiped"):
                context.update_data(game_hall_swiped=True)
                return self._execute(self._hall_swipe_action, context)
            if self._has_text(context, self._online_play_text):
                return self._tap_feature_or_point(
                    context, self._online_play_key, self._carousel_action
                )
            # 在线玩 OCR 未命中时退到旧轮播图入口（仍在游戏大厅内）。
            return self._execute(self._carousel_action, context)

        # 游戏中心：OCR 识别到「在线玩」后，按顺序点击游戏卡按钮坐标。
        # 部分卡片是「下载游戏」详情页，点进去后恢复流程会返回 GAME_CENTER，
        # 下一次自动换下一张卡片，直到进入可玩的登录/运行页。
        if state is PageState.GAME_CENTER:
            if self._has_text(context, self._online_play_text):
                attempts = int(context.get("game_center_attempts", 0))
                points = self._game_center_online_play_points
                action = points[attempts % len(points)]
                context.update_data(game_center_attempts=attempts + 1)
                return self._execute(action, context)
            return self._execute(self._carousel_action, context)

        # 登录/协议页：先勾选协议，再点「登录游戏 / 进入游戏」。
        if state is PageState.GAME_LOADING:
            return self._handle_loading_like(context)

        if state is PageState.GAME_MENU:
            return self._execute(Action.tap_feature(self._exit_menu_key), context)

        if state is PageState.GAME_EXIT_CONFIRM:
            return self._execute(Action.tap_feature(self._close_game_key), context)

        # QQR-17：奖励页可能出现两种布局：
        # 1. 直接看到「去玩游戏」按钮 → 点按钮；
        # 2. 只看到「玩游戏领赠币」游戏卡 → 先点游戏卡，进入 GAME_ENTRY 后再点按钮。
        # 两者都不在屏幕内时，先按旧 pipeline 的坐标滚动查找。
        # QQR-18：游戏退出后回到奖励页，则尝试领取游戏赠币。
        if state is PageState.REWARD_HOME:
            if context.get("game_exit_done"):
                if self._has_text(context, self._claim_text):
                    return self._execute(
                        Action.tap_feature(self._claim_key), context
                    )
                return StepResult(
                    "游戏已退出，奖励页暂未出现可领取按钮",
                    actions=(),
                    progress=False,
                )
            if self._has_text(context, self._go_play_text):
                context.update_data(game_entry_scrolls=0)
                return self._tap_feature_or_point(
                    context, self._go_play_key, self._reward_game_button_action
                )
            if self._has_text(context, self._reward_entry_text):
                # 只识别到游戏卡标题时，OCR 可能没读到右侧按钮文字；
                # 直接点击旧 pipeline 标定的按钮坐标 fallback。
                context.update_data(game_entry_scrolls=0)
                return self._execute(self._reward_game_button_action, context)
            if self._entry_scroll_action is not None:
                attempts = int(context.get("game_entry_scrolls", 0))
                if attempts < self._max_entry_scrolls:
                    context.update_data(game_entry_scrolls=attempts + 1)
                    return self._execute(self._entry_scroll_action, context)
        elif state is PageState.GAME_ENTRY:
            # 奖励页游戏卡也可能被识别成 GAME_ENTRY；游戏退出后这里必须
            # 走「领取赠币」而不是再次进入游戏。
            if context.get("game_exit_done"):
                if self._has_text(context, self._claim_text):
                    return self._execute(
                        Action.tap_feature(self._claim_key), context
                    )
                return StepResult(
                    "游戏已退出，奖励页暂未出现可领取按钮",
                    actions=(),
                    progress=False,
                )
            return self._tap_feature_or_point(
                context, self._go_play_key, self._reward_game_button_action
            )

        if state is PageState.GAME_RUNNING:
            # QQR-20：游戏加载/协议页也可能出现「领币」，必须先等真正进入
            # 游戏运行态后再开始计时，否则会提前退出。
            if self._has_any_text(context, self._RUNNING_BLOCK_TEXTS):
                context.update_data(game_started_at=None)
                return self._handle_loading_like(
                    context, note="游戏仍在加载/协议页，暂不计时"
                )
            started = context.get("game_started_at")
            if started is None:
                context.update_data(game_started_at=context.now)
                return StepResult(
                    "确认游戏运行，开始挂机计时",
                    actions=("GAME_TIMER_START",),
                    progress=True,
                )
            if context.now - float(started) >= self._game_duration:
                if not context.get("game_exit_started"):
                    # QQR-18：点击右侧「领币」悬浮窗（OCR 定位后取右下角热点）。
                    context.update_data(
                        game_exit_started=True,
                        game_exit_done=True,
                    )
                    return self._execute(self._exit_action, context)
                return StepResult(
                    "已点击领币，等待延伸菜单出现",
                    actions=(),
                    progress=False,
                )
        return super().advance(context)

    def _handle_loading_like(
        self, context: TaskContext, *, note: str = "等待游戏加载/协议页"
    ) -> StepResult:
        """处理登录/协议/加载页（即使被误判成 GAME_RUNNING 也走这里）。"""
        if self._has_text(context, self._agreement_text):
            clicks = int(context.get("game_agreement_clicks", 0))
            if clicks < len(self._agreement_actions):
                context.update_data(game_agreement_clicks=clicks + 1)
                return self._execute(self._agreement_actions[clicks], context)
        if self._has_text(context, self._login_game_text):
            return self._execute(Action.tap_feature(self._login_game_key), context)
        if self._has_text(context, DEFAULT_FEATURE_KEYS.game_ocr_enter_alt):
            return self._execute(Action.tap_feature(self._enter_game_alt_key), context)
        if self._has_text(context, DEFAULT_FEATURE_KEYS.game_ocr_enter):
            return self._execute(Action.tap_feature(self._enter_game_key), context)
        if (
            self._has_text(context, self._agree_text)
            and not context.get("game_agree_clicked")
        ):
            context.update_data(game_agree_clicked=True)
            return self._execute(Action.tap_feature(self._agree_key), context)
        return StepResult(note, actions=(), progress=False)

    def _tap_feature_or_point(
        self,
        context: TaskContext,
        feature_key: str,
        fallback: Optional[Action],
    ) -> StepResult:
        """先按 OCR/模板定位点击；定位失败时退到固定坐标 fallback。"""
        step = self._execute(Action.tap_feature(feature_key), context)
        if not step.progress and fallback is not None:
            return self._execute(fallback, context)
        return step

    @staticmethod
    def _has_text(context: TaskContext, needle: str) -> bool:
        return any(needle in text for text in context.observation.ocr_texts)

    def _has_any_text(self, context: TaskContext, needles: tuple) -> bool:
        return any(
            any(needle in text for text in context.observation.ocr_texts)
            for needle in needles
        )


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
    contract = build_game_contract(keys, timeout_seconds=timeout_seconds)
    if entry_scroll_action is None:
        # 旧 pipeline GameScrollToPlay 的坐标，作为配置化之前的滚动兜底；
        # 仅用于奖励页游戏入口不在当前屏时查找，不做任何点击。
        entry_scroll_action = Action.swipe(360, 980, 360, 420, 500)
    adapter = GameTaskAdapter(
        game_duration_seconds=game_duration_seconds,
        # QQR-18：计时到点后点击右侧「领币」悬浮窗右下角热点。
        exit_action=Action.tap_point(695, 302),
        device=device,
        plan=build_game_action_plan(keys),
        expected_package=keys.qq_reader_package,
        popup_feature=feature_key(keys, keys.popup_close),
        reward_entry_key=feature_key(keys, keys.game_ocr_reward_entry),
        go_play_key=feature_key(keys, keys.game_ocr_go_play),
        reward_entry_text=keys.game_ocr_reward_entry,
        go_play_text=keys.game_ocr_go_play,
        enter_game_key=feature_key(keys, keys.game_ocr_enter),
        enter_game_alt_key=feature_key(keys, keys.game_ocr_enter_alt),
        exit_menu_key=feature_key(keys, keys.game_ocr_exit),
        close_game_key=feature_key(keys, keys.game_ocr_close_game),
        claim_key=feature_key(keys, keys.game_ocr_claim),
        online_play_key=feature_key(keys, keys.game_ocr_online_play),
        agree_key=feature_key(keys, keys.game_ocr_agree),
        login_game_key=feature_key(keys, keys.game_ocr_login_game),
        agreement_text=keys.game_ocr_agreement,
        claim_text=keys.game_ocr_claim,
        agree_text=keys.game_ocr_agree,
        online_play_text=keys.game_ocr_online_play,
        login_game_text=keys.game_ocr_login_game,
        carousel_action=Action.tap_point(360, 360),
        hall_swipe_action=Action.swipe(360, 420, 360, 980, 500),
        game_center_online_play_points=(
            Action.tap_point(98, 981),
            Action.tap_point(254, 981),
            Action.tap_point(408, 980),
            Action.tap_point(564, 982),
        ),
        agreement_action=Action.tap_point(157, 1032),
        agreement_action_alt=Action.tap_point(152, 1066),
        entry_scroll_action=entry_scroll_action,
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
