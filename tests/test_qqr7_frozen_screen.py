"""QQR-7 / QQR-FIX1：画面冻结安全网不得打断「有意静止」的计时挂机。

锁定行为：
* 适配器在计时挂机的步骤上声明 ``StepResult.hold_until``（挂机截止时刻）。
  截止之前这些轮次不计入画面冻结：静止画面挂机满时长不触发任何恢复动作
  （游戏运行帧、QQR-36 公告帧；命令行 22/30 分钟与 GUI 25/35 分钟两组默认值）。
* 没有声明、或已过截止时刻仍声明的轮次照常计入：误判成挂机态的真冻结页面
  （原 QQR-FIX1 场景）仍会触发恢复，计时进行中也一样。
* 阈值由 ``RunnerConfig.frozen_screen_rounds`` 配置（默认 18 轮）。

全部是 FakeClock 离线模拟，不涉及识别资源。
"""

from __future__ import annotations

import pytest

from qqreader.contract.outcome import TaskOutcome
from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.observation import PageObservation
from qqreader.page.states import Orientation, PageState
from qqreader.recovery.policy import EscalationPolicy, RecoveryAction
from qqreader.runner.runner import RunnerConfig, TaskRunner
from qqreader.runtime.clock import FakeClock
from qqreader.runtime.context import StepResult
from qqreader.tasks import feature_key
from qqreader.tasks.game import build_game_definition
from tests.helpers import (
    QQ,
    FakeAdapter,
    PageFlowObserver,
    QueueObserver,
    SimulatedDevice,
    game_close_confirm_observation,
    game_hall_observation,
    game_menu_observation,
    game_running_observation,
    home_observation,
    make_contract,
    make_definition,
    make_recognizer,
    reward_done_observation,
)

KEYS = DEFAULT_FEATURE_KEYS
POPUP_CLOSE_KEY = feature_key(KEYS, KEYS.popup_close)
GAME_EXIT_MENU_KEY = feature_key(KEYS, KEYS.game_ocr_exit)
GAME_CLOSE_GAME_KEY = feature_key(KEYS, KEYS.game_ocr_close_game)
TOUCH_PREFIXES = ("TAP", "PRESS_BACK", "SWIPE")

#: QQR-36 真机公告帧（与 ``tests/test_qqr36_announcement.py`` 相同），静态公告页也算挂机页。
ANNOUNCEMENT = PageObservation(
    current_app=QQ,
    orientation=Orientation.PORTRAIT,
    ocr_texts=("亲爱的仙使大人：", "一、全新功能", "适齿"),
)
#: 卡在「正在连接服务器」的加载页：「领币」悬浮窗还在，识别器确认成 GAME_RUNNING，
#: 适配器认出加载文案、不计时也不声明静止——误判成挂机态的真冻结页面。
CONNECTING = game_running_observation(ocr_texts=("领币", "正在连接服务器"))

HANG_FRAMES = pytest.mark.parametrize(
    "frame", [game_running_observation(), ANNOUNCEMENT], ids=["running", "announcement"]
)


def _run_game(observer, device, *, duration_min: float, timeout_min: float):
    definition = build_game_definition(
        KEYS,
        observer,
        device,
        EscalationPolicy(),
        make_recognizer(),
        timeout_seconds=timeout_min * 60.0,
        game_duration_seconds=duration_min * 60.0,
    )
    return TaskRunner(definition, FakeClock()).run()


def _kinds(result) -> list:
    return [event.kind for event in result.diagnostics]


def _advances(result) -> list:
    return [event for event in result.diagnostics if event.kind == "step.advance"]


def _is_touch(event) -> bool:
    return any(str(action).startswith(TOUCH_PREFIXES) for action in event.data["actions"])


def _assert_no_recovery(result, device) -> None:
    kinds = _kinds(result)
    assert "safety.frozen_screen" not in kinds
    assert "recovery.action" not in kinds
    assert result.recovery_history == ()
    # 修复前：9.2 分钟点 popup_close，15.2 分钟 launch_app，18.2 分钟 stop+launch 杀掉游戏。
    assert ("tap_feature", POPUP_CLOSE_KEY) not in device.calls
    assert [call for call in device.calls if call[0] in ("launch_app", "stop_app")] == []


# ------------------------------------------------------------------ 静止画面挂机


@HANG_FRAMES
@pytest.mark.parametrize(
    ("duration_min", "timeout_min"), [(22, 30), (25, 35)], ids=["cli-22min", "gui-25min"]
)
def test_static_frame_hang_full_duration_triggers_no_recovery(
    frame: PageObservation, duration_min: float, timeout_min: float
) -> None:
    """观测器恒返回同一帧：挂机满时长前不碰设备，整个运行不触发任何恢复。"""
    device = SimulatedDevice()

    result = _run_game(
        QueueObserver([frame]), device, duration_min=duration_min, timeout_min=timeout_min
    )

    _assert_no_recovery(result, device)
    advances = _advances(result)
    touches = [event for event in advances if _is_touch(event)]
    assert touches, "挂机到点后应执行退出动作"
    # 第一次触控就是挂机到点后的退出动作；之前每一轮都声明了同一个挂机截止时刻。
    assert touches[0].at >= duration_min * 60
    hang = advances[: advances.index(touches[0])]
    assert hang and all(
        event.data["hold_until"] == duration_min * 60 for event in hang
    )
    # 恒定帧永远回不到奖励页，最终是独立超时；这里只关心挂机没被恢复动作打断。
    assert result.outcome is TaskOutcome.TIMEOUT


@HANG_FRAMES
def test_static_frame_hang_then_exit_completes_successfully(
    frame: PageObservation,
) -> None:
    """挂机期间画面始终不变，到点后正常退出并回到奖励页，全程没有恢复动作。"""
    observer = PageFlowObserver(
        pages={
            "HANG": frame,
            "GAME_MENU": game_menu_observation(),
            "GAME_EXIT_CONFIRM": game_close_confirm_observation(),
            "GAME_HALL": game_hall_observation(),
            "REWARD_DONE": reward_done_observation(),
        },
        start="HANG",
    )

    def on_tap_point(x: int, y: int) -> None:
        if (x, y) == (695, 302) and observer.page == "HANG":
            observer.go("GAME_MENU")

    def on_tap_feature(name: str) -> None:
        if name == GAME_EXIT_MENU_KEY:
            observer.go("GAME_EXIT_CONFIRM")
        elif name == GAME_CLOSE_GAME_KEY:
            observer.go("GAME_HALL")

    def on_press_back() -> None:
        # 公告页到点按返回退出；游戏大厅再返回一次回到奖励页。
        if observer.page == "HANG":
            observer.go("GAME_HALL")
        elif observer.page == "GAME_HALL":
            observer.go("REWARD_DONE")

    device = SimulatedDevice(
        on_tap_feature=on_tap_feature,
        on_tap_point=on_tap_point,
        on_press_back=on_press_back,
    )

    result = _run_game(observer, device, duration_min=22, timeout_min=30)

    assert result.outcome is TaskOutcome.SUCCESS
    assert result.final_state is PageState.REWARD_HOME
    _assert_no_recovery(result, device)
    touches = [event for event in _advances(result) if _is_touch(event)]
    assert touches[0].at >= 22 * 60


# ------------------------------------------------------------------ 真冻结仍恢复


def test_frozen_page_misjudged_as_running_still_triggers_recovery() -> None:
    """原 QQR-FIX1 场景：页面被确认成挂机态，实际是卡住不动的加载页。"""
    assert make_recognizer().evaluate(CONNECTING).state is PageState.GAME_RUNNING
    device = SimulatedDevice()

    result = _run_game(QueueObserver([CONNECTING]), device, duration_min=22, timeout_min=10)

    kinds = _kinds(result)
    assert "safety.frozen_screen" in kinds
    # 第 1 轮建立 OCR 签名，之后默认连续 18 轮不变才触发。
    first = kinds.index("safety.frozen_screen")
    assert kinds[:first].count("step.advance") == 1 + 18
    # 适配器没把它当挂机：没开始计时，也没声明有意静止。
    advances = _advances(result)
    assert "开始挂机计时" not in " ".join(event.message for event in advances)
    assert all("hold_until" not in event.data for event in advances)
    actions = [step.action for step in result.recovery_history]
    assert actions[:3] == [
        RecoveryAction.RESCREENSHOT.value,
        RecoveryAction.REEVALUATE_STATE.value,
        RecoveryAction.DISMISS_POPUP.value,
    ]
    assert ("tap_feature", POPUP_CLOSE_KEY) in device.calls
    assert result.outcome is TaskOutcome.TIMEOUT


def test_frozen_reconnect_page_during_hang_still_triggers_recovery() -> None:
    """计时开始后画面卡在重连页：重连页那几轮不是有意静止，计时进行中也照常累计。"""
    observer = QueueObserver([game_running_observation()] * 3 + [CONNECTING])
    device = SimulatedDevice()

    result = _run_game(observer, device, duration_min=22, timeout_min=10)

    advances = _advances(result)
    assert advances[0].message == "确认游戏运行，开始挂机计时"
    assert advances[0].data["hold_until"] == 22 * 60
    reconnect = [
        event for event in advances
        if event.message == "游戏重新出现加载/协议页，保留已累计挂机时间"
    ]
    assert reconnect and all("hold_until" not in event.data for event in reconnect)
    frozen = [event for event in result.diagnostics if event.kind == "safety.frozen_screen"]
    assert frozen and frozen[0].at < 22 * 60
    assert result.recovery_history


# ------------------------------------------------------------------ 调度核心（通用）


def _frozen_contract(timeout_seconds: float):
    return make_contract(name="qqr7_frozen", timeout_seconds=timeout_seconds)


def _waiting_adapter(seconds: float, *, hold_until=None) -> FakeAdapter:
    """每轮在同一画面上等待 ``seconds``（与 PlannedTaskAdapter 的 WAIT 一样在适配器内睡眠）。"""
    step = StepResult(
        f"等待 {seconds:g}s", actions=("WAIT",), progress=True, hold_until=hold_until
    )
    return FakeAdapter(
        steps=[step] * 500,
        on_advance=lambda ctx: ctx.clock.sleep(seconds, ctx.token),
    )


def test_frozen_screen_threshold_defaults_to_18_and_is_validated() -> None:
    assert RunnerConfig().frozen_screen_rounds == 18
    with pytest.raises(ValueError):
        RunnerConfig(frozen_screen_rounds=0)


def test_undeclared_wait_on_frozen_screen_recovers_after_configured_rounds() -> None:
    """只有 WAIT、没有声明有意静止：照旧按阈值触发（阈值来自 RunnerConfig）。"""
    adapter = _waiting_adapter(10.0)
    definition = make_definition(
        _frozen_contract(120.0), QueueObserver([home_observation()]), adapter
    )

    result = TaskRunner(
        definition, FakeClock(), config=RunnerConfig(frozen_screen_rounds=5)
    ).run()

    kinds = _kinds(result)
    first = kinds.index("safety.frozen_screen")
    assert kinds[:first].count("step.advance") == 1 + 5
    event = result.diagnostics[first]
    assert "连续 5 轮" in event.message
    assert event.data["rounds"] == 5
    assert adapter.recoveries[0] is RecoveryAction.RESCREENSHOT


def test_hold_rounds_are_exempt_only_until_declared_deadline() -> None:
    """截止前声明静止的轮次不计入；过了截止时刻仍声明的轮次照常累计。"""
    adapter = _waiting_adapter(10.0, hold_until=300.0)
    definition = make_definition(
        _frozen_contract(600.0), QueueObserver([home_observation()]), adapter
    )

    result = TaskRunner(
        definition, FakeClock(), config=RunnerConfig(frozen_screen_rounds=5)
    ).run()

    frozen = [event for event in result.diagnostics if event.kind == "safety.frozen_screen"]
    assert frozen, "过期的静止声明不能无限压住安全网"
    # 0–290s 开始的 30 轮都在截止前；从 300s 那轮起计数，5 轮后（350s）触发。
    assert frozen[0].at == pytest.approx(300.0 + 5 * 10.0)
    assert adapter.recoveries[0] is RecoveryAction.RESCREENSHOT


def test_hold_rounds_before_deadline_never_trigger() -> None:
    adapter = _waiting_adapter(10.0, hold_until=10_000.0)
    definition = make_definition(
        _frozen_contract(600.0), QueueObserver([home_observation()]), adapter
    )

    result = TaskRunner(
        definition, FakeClock(), config=RunnerConfig(frozen_screen_rounds=5)
    ).run()

    assert result.outcome is TaskOutcome.TIMEOUT
    assert "safety.frozen_screen" not in _kinds(result)
    assert adapter.recoveries == []
