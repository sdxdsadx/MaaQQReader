"""QQReader 单元测试共享工具：观测脚本、假设备、假适配器与状态构造。"""

from __future__ import annotations

from collections import deque
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from qqreader.captcha.guard import CaptchaOutcome, CaptchaResolution
from qqreader.contract.contract import FatalErrorSpec, RecoverableErrorSpec, TaskContract, TimeoutSpec
from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS, FeatureKeys
from qqreader.page.observation import PageObservation
from qqreader.page.profiles import build_default_state_definitions
from qqreader.page.recognizer import PageStateRecognizer
from qqreader.page.states import Orientation, PageState
from qqreader.recovery.policy import EscalationPolicy, RecoveryAction
from qqreader.runtime.clock import CancellationToken, FakeClock
from qqreader.runtime.context import StepResult, TaskContext

QQ = DEFAULT_FEATURE_KEYS.qq_reader_package


# --------------------------------------------------------------------- 观测构造


def make_recognizer(keys: FeatureKeys = DEFAULT_FEATURE_KEYS) -> PageStateRecognizer:
    return PageStateRecognizer(build_default_state_definitions(keys))


def home_observation(**overrides: object) -> PageObservation:
    base = dict(
        current_app=QQ,
        orientation=Orientation.PORTRAIT,
        ocr_texts=("书架",),
        icons={"home.nav_my": 0.95},
        structure={"home.bottom_nav": 0.9},
    )
    base.update(overrides)
    return PageObservation(**base)  # type: ignore[arg-type]


def reward_observation(ocr: Tuple[str, ...] = ("今日已获赠币", "看小视频领好礼", "立即观看"), **overrides: object) -> PageObservation:
    base = dict(
        current_app=QQ,
        orientation=Orientation.PORTRAIT,
        ocr_texts=ocr,
        icons={"reward.header": 0.9},
        structure={"reward.bottom_nav": 0.8},
    )
    base.update(overrides)
    return PageObservation(**base)  # type: ignore[arg-type]


def ad_playing_observation(**overrides: object) -> PageObservation:
    base = dict(
        current_app=QQ,
        orientation=Orientation.PORTRAIT,
        ocr_texts=("广告", "跳过"),
        icons={"ad.skip": 0.9},
        structure={"ad.video_surface": 0.8},
    )
    base.update(overrides)
    return PageObservation(**base)  # type: ignore[arg-type]


def ad_result_observation(**overrides: object) -> PageObservation:
    base = dict(
        current_app=QQ,
        orientation=Orientation.PORTRAIT,
        ocr_texts=("奖品已发放",),
        icons={"ad.result_close": 0.9},
        structure={"ad.video_surface": 0.7},
    )
    base.update(overrides)
    return PageObservation(**base)  # type: ignore[arg-type]


def captcha_observation(**overrides: object) -> PageObservation:
    base = dict(
        current_app=QQ,
        orientation=Orientation.PORTRAIT,
        ocr_texts=("请在下图依次点击",),
        structure={"captcha.overlay": 0.8},
    )
    base.update(overrides)
    return PageObservation(**base)  # type: ignore[arg-type]


def game_entry_observation(**overrides: object) -> PageObservation:
    """奖励页游戏卡点击后、出现「去玩游戏」按钮的中间页。"""
    base = dict(
        current_app=QQ,
        orientation=Orientation.PORTRAIT,
        ocr_texts=("玩游戏领赠币", "去玩游戏"),
    )
    base.update(overrides)
    return PageObservation(**base)  # type: ignore[arg-type]


def game_agreement_observation(**overrides: object) -> PageObservation:
    """小游戏登录/协议页：需要勾选协议后点「进入游戏」。"""
    base = dict(
        current_app=QQ,
        orientation=Orientation.PORTRAIT,
        ocr_texts=("我已详细阅读并同意", "进入游戏"),
    )
    base.update(overrides)
    return PageObservation(**base)  # type: ignore[arg-type]


def game_menu_observation(**overrides: object) -> PageObservation:
    """点击右侧「领币」后出现的延伸菜单。"""
    base = dict(
        current_app=QQ,
        orientation=Orientation.PORTRAIT,
        ocr_texts=("领币", "退出"),
    )
    base.update(overrides)
    return PageObservation(**base)  # type: ignore[arg-type]


def game_close_confirm_observation(**overrides: object) -> PageObservation:
    """退出游戏确认弹窗：关闭游戏。"""
    base = dict(
        current_app=QQ,
        orientation=Orientation.PORTRAIT,
        ocr_texts=("退出", "关闭游戏"),
    )
    base.update(overrides)
    return PageObservation(**base)  # type: ignore[arg-type]


def game_loading_observation(**overrides: object) -> PageObservation:
    base = dict(
        current_app=QQ,
        orientation=Orientation.LANDSCAPE,
        ocr_texts=("点击选服",),
        templates={"game.login_button": 0.8},
        structure={"game.loading_marker": 0.7},
    )
    base.update(overrides)
    return PageObservation(**base)  # type: ignore[arg-type]


def game_hall_observation(**overrides: object) -> PageObservation:
    """「去玩游戏」点击后的游戏大厅/加载页（旧 pipeline GameHallRetry）。"""
    base = dict(
        current_app=QQ,
        orientation=Orientation.PORTRAIT,
        ocr_texts=("精选大作", "今日必玩推荐", "排行", "分类", "在线玩"),
    )
    base.update(overrides)
    return PageObservation(**base)  # type: ignore[arg-type]


def game_center_observation(**overrides: object) -> PageObservation:
    """点击游戏大厅「在线玩」后进入的游戏中心页。"""
    base = dict(
        current_app=QQ,
        orientation=Orientation.PORTRAIT,
        ocr_texts=("游戏中心", "在线玩", "精品热门", "大家都在玩"),
    )
    base.update(overrides)
    return PageObservation(**base)  # type: ignore[arg-type]


def game_running_observation(**overrides: object) -> PageObservation:
    base = dict(
        current_app=QQ,
        orientation=Orientation.LANDSCAPE,
        ocr_texts=("领币",),
        structure={"game.hud": 0.9},
    )
    base.update(overrides)
    return PageObservation(**base)  # type: ignore[arg-type]


def game_result_observation(**overrides: object) -> PageObservation:
    base = dict(
        current_app=QQ,
        orientation=Orientation.PORTRAIT,
        ocr_texts=("退出",),
        templates={"game.exit_dialog": 0.8},
        icons={"game.exit_menu": 0.9},
    )
    base.update(overrides)
    return PageObservation(**base)  # type: ignore[arg-type]


def reward_done_observation(
    text: str = "玩游戏领赠币 明日再来", **overrides: object
) -> PageObservation:
    return reward_observation(ocr=(text, "今日已获赠币"), **overrides)


def reward_claim_observation(**overrides: object) -> PageObservation:
    """游戏时长满足后，奖励页出现「立即领取」按钮。"""
    return reward_observation(
        ocr=("今日已获赠币", "玩游戏领赠币+20赠币", "立即领取"),
        **overrides,
    )


# --------------------------------------------------------------------- 假对象


class QueueObserver:
    """按脚本返回观测；脚本耗尽后重复最后一帧。"""

    def __init__(self, script: Sequence[PageObservation], repeat_last: bool = True) -> None:
        if not script:
            raise ValueError("script 不能为空")
        self._queue = deque(script)
        self._last = script[-1]
        self._repeat_last = repeat_last
        self.calls = 0

    def push(self, observation: PageObservation) -> None:
        self._queue.append(observation)

    def observe(self, context: TaskContext, *, deep: bool = False) -> PageObservation:
        self.calls += 1
        if self._queue:
            self._last = self._queue.popleft()
        elif not self._repeat_last:
            raise RuntimeError("观测脚本已耗尽")
        return self._last


class PageFlowObserver:
    """用「当前页面」模拟真实设备：点击回调改变页面，可选按时间自动跳转。

    ``auto_transitions`` 形如 ``{"AD_PLAYING": ("AD_RESULT", 5.0)}``，
    表示停留在该页面超过 ``delay`` 秒后自动进入下一页。
    """

    def __init__(
        self,
        pages: Dict[str, PageObservation],
        start: str,
        auto_transitions: Optional[Dict[str, Tuple[str, float]]] = None,
    ) -> None:
        if start not in pages:
            raise ValueError(f"未知起始页面: {start}")
        self._pages = dict(pages)
        self._auto = dict(auto_transitions or {})
        self._deadlines: Dict[str, float] = {}
        self.page = start
        self.calls = 0

    def go(self, page: str) -> None:
        if page not in self._pages:
            raise ValueError(f"未知页面: {page}")
        self.page = page
        self._deadlines.pop(page, None)

    def observe(self, context: TaskContext, *, deep: bool = False) -> PageObservation:
        self.calls += 1
        transition = self._auto.get(self.page)
        if transition is not None:
            next_page, delay = transition
            deadline = self._deadlines.get(self.page)
            if deadline is None:
                self._deadlines[self.page] = context.now + delay
            elif context.now >= deadline:
                self.go(next_page)
        return self._pages[self.page]


class SimulatedDevice:
    """记录调用并可对点击特征/坐标/返回键回调（用于驱动观测脚本）。"""
    def __init__(
        self,
        on_tap_feature: Optional[Callable[[str], None]] = None,
        tap_results: Optional[Dict[str, bool]] = None,
        on_tap_point: Optional[Callable[[int, int], None]] = None,
        on_press_back: Optional[Callable[[], None]] = None,
    ) -> None:
        self.calls: List[Tuple[object, ...]] = []
        self._on_tap_feature = on_tap_feature
        self._tap_results = tap_results or {}
        self._on_tap_point = on_tap_point
        self._on_press_back = on_press_back

    def tap_feature(self, name: str) -> bool:
        self.calls.append(("tap_feature", name))
        ok = self._tap_results.get(name, True)
        if ok and self._on_tap_feature is not None:
            self._on_tap_feature(name)
        return ok

    def tap_point(self, x: int, y: int) -> None:
        self.calls.append(("tap_point", x, y))
        if self._on_tap_point is not None:
            self._on_tap_point(x, y)

    def swipe(self, x0: int, y0: int, x1: int, y1: int, duration_ms: int = 300) -> None:
        self.calls.append(("swipe", x0, y0, x1, y1, duration_ms))

    def press_back(self) -> None:
        self.calls.append(("press_back",))
        if self._on_press_back is not None:
            self._on_press_back()

    def launch_app(self, package: str) -> None:
        self.calls.append(("launch_app", package))

    def stop_app(self, package: str) -> None:
        self.calls.append(("stop_app", package))


class FakeAdapter:
    """记录 advance / recover 的假适配器。"""

    def __init__(
        self,
        steps: Optional[Sequence[StepResult]] = None,
        on_advance: Optional[Callable[[TaskContext], None]] = None,
        on_recover: Optional[Callable[[RecoveryAction, TaskContext], None]] = None,
    ) -> None:
        self.advances: List[PageState] = []
        self.recoveries: List[RecoveryAction] = []
        self._steps = list(steps or [])
        self._on_advance = on_advance
        self._on_recover = on_recover

    def advance(self, context: TaskContext) -> StepResult:
        self.advances.append(context.state)
        if self._on_advance is not None:
            self._on_advance(context)
        if self._steps:
            return self._steps.pop(0)
        return StepResult("假适配器推进", progress=True)

    def recover(self, action: RecoveryAction, context: TaskContext) -> StepResult:
        self.recoveries.append(action)
        if self._on_recover is not None:
            self._on_recover(action, context)
        return StepResult(f"假适配器恢复 {action.value}", progress=True)


class StubCaptchaGuard:
    """按脚本返回验证码处理结论的假守卫。"""

    def __init__(self, outcomes: Optional[Sequence[CaptchaOutcome]] = None) -> None:
        self.calls = 0
        self._outcomes = list(outcomes or [])
        self._default = CaptchaOutcome(
            resolution=CaptchaResolution.WAITING_FOR_HUMAN,
            attempts=0,
            detail="stub guard：等待人工",
        )

    def handle(self, context: TaskContext) -> CaptchaOutcome:
        self.calls += 1
        if self._outcomes:
            return self._outcomes.pop(0)
        return self._default


class FakeSolver:
    """按脚本返回求解结果。"""

    def __init__(self, results: Sequence[object]) -> None:
        self.calls = 0
        self._results = list(results)

    def solve(self, context: TaskContext):  # noqa: ANN201 - 返回 SolveResult
        self.calls += 1
        if not self._results:
            from qqreader.captcha.guard import SolveResult

            return SolveResult(False, "脚本耗尽")
        return self._results.pop(0)


# --------------------------------------------------------------------- 契约构造


def make_contract(
    *,
    name: str = "test_task",
    start_condition=None,
    ready_condition=None,
    progress_condition=None,
    captcha_condition=None,
    success_condition=None,
    recoverable_error: Tuple[RecoverableErrorSpec, ...] = (),
    fatal_error: Tuple[FatalErrorSpec, ...] = (),
    timeout_seconds: float = 60.0,
) -> TaskContract:
    from qqreader.contract.conditions import Always, Never, state_in

    return TaskContract(
        name=name,
        description="测试契约",
        start_condition=start_condition or Always(),
        ready_condition=ready_condition or Always(),
        progress_condition=progress_condition or Always(),
        captcha_condition=captcha_condition or Never(),
        success_condition=success_condition or Never(),
        recoverable_error=recoverable_error,
        fatal_error=fatal_error,
        timeout=TimeoutSpec(timeout_seconds),
    )


def make_context(
    observation: PageObservation,
    *,
    contract: Optional[TaskContract] = None,
    clock: Optional[FakeClock] = None,
    token: Optional[CancellationToken] = None,
    run_state=None,
) -> TaskContext:
    from qqreader.page.states import RunState

    recognizer = make_recognizer()
    decision = recognizer.evaluate(observation)
    context = TaskContext(
        contract=contract or make_contract(),
        clock=clock or FakeClock(),
        token=token or CancellationToken(),
        started_at=0.0,
    )
    context.update_observation(observation, decision)
    context.run_state = run_state or RunState.IDLE
    return context


def make_definition(
    contract: TaskContract,
    observer,
    adapter,
    *,
    recovery=None,
    captcha_guard=None,
    recognizer=None,
    confirmer=None,
):
    from qqreader.runner.definition import TaskDefinition

    return TaskDefinition(
        contract=contract,
        observer=observer,
        adapter=adapter,
        recovery=recovery or EscalationPolicy(),
        captcha_guard=captcha_guard or StubCaptchaGuard(),
        state_recognizer=recognizer or make_recognizer(),
        confirmer=confirmer,
    )
