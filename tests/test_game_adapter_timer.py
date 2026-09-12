"""游戏挂机计时与广告/游戏端到端流程（使用真实契约 + 真实适配器）。"""

from __future__ import annotations

import pytest

from qqreader.contract.outcome import TaskOutcome
from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.states import RunState
from qqreader.recovery.policy import EscalationPolicy
from qqreader.runner.runner import TaskRunner
from qqreader.runtime.clock import FakeClock
from qqreader.tasks import (
    Action,
    ActionKind,
    GameTaskAdapter,
    build_ad_definition,
    build_game_action_plan,
    build_game_contract,
    build_game_definition,
    feature_key,
)
from tests.helpers import (
    QQ,
    PageFlowObserver,
    SimulatedDevice,
    ad_playing_observation,
    ad_result_observation,
    game_agreement_observation,
    game_center_observation,
    game_close_confirm_observation,
    game_entry_observation,
    game_hall_observation,
    game_loading_observation,
    game_menu_observation,
    game_running_observation,
    home_observation,
    reward_claim_observation,
    make_context,
    make_recognizer,
    reward_done_observation,
    reward_observation,
)

KEYS = DEFAULT_FEATURE_KEYS

HOME_REWARD_KEY = feature_key(KEYS, KEYS.home_ocr_reward_entry)
REWARD_WATCH_KEY = feature_key(KEYS, KEYS.reward_ocr_watch)
AD_SKIP_KEY = feature_key(KEYS, KEYS.ad_ocr_skip)
AD_RESULT_CLOSE_KEY = feature_key(KEYS, KEYS.ad_result_close)
GAME_REWARD_ENTRY_KEY = feature_key(KEYS, KEYS.game_ocr_reward_entry)
GAME_GO_PLAY_KEY = feature_key(KEYS, KEYS.game_ocr_go_play)
GAME_ENTER_KEY = feature_key(KEYS, KEYS.game_ocr_enter)
GAME_EXIT_MENU_KEY = feature_key(KEYS, KEYS.game_ocr_exit)
GAME_CLOSE_GAME_KEY = feature_key(KEYS, KEYS.game_ocr_close_game)
GAME_CLAIM_KEY = feature_key(KEYS, KEYS.game_ocr_claim)
GAME_ONLINE_PLAY_KEY = feature_key(KEYS, KEYS.game_ocr_online_play)
GAME_LOGIN_KEY = feature_key(KEYS, KEYS.game_ocr_login_game)
POPUP_CLOSE_KEY = feature_key(KEYS, KEYS.popup_close)


def _make_game_adapter(device, duration: float) -> GameTaskAdapter:
    return GameTaskAdapter(
        game_duration_seconds=duration,
        exit_action=Action.tap_point(695, 302),
        device=device,
        plan=build_game_action_plan(KEYS),
        expected_package=QQ,
        popup_feature=POPUP_CLOSE_KEY,
    )


def test_game_timer_starts_only_after_running_and_exits_after_duration() -> None:
    clock = FakeClock()
    device = SimulatedDevice()
    adapter = _make_game_adapter(device, duration=60.0)
    contract = build_game_contract(KEYS)

    loading = make_context(
        game_loading_observation(
            ocr_texts=("登录游戏",),
            templates={},
            structure={},
        ),
        contract=contract,
        clock=clock,
        run_state=RunState.RUNNING,
    )
    adapter.advance(loading)
    assert loading.get("game_started_at") is None
    assert device.calls == [("tap_feature", GAME_LOGIN_KEY)]

    running = make_context(
        game_running_observation(), contract=contract, clock=clock, run_state=RunState.RUNNING
    )
    first = adapter.advance(running)
    assert first.actions == ("GAME_TIMER_START",)
    assert running.get("game_started_at") == 0.0

    waiting = adapter.advance(running)
    assert waiting.actions == (ActionKind.WAIT.value,)
    assert clock.now() == 10.0
    assert ("tap_point", 695, 302) not in device.calls

    clock.advance(50.0)  # 累计 60s，达到挂机时长
    exiting = adapter.advance(running)
    assert exiting.actions == (ActionKind.TAP_POINT.value,)
    assert ("tap_point", 695, 302) in device.calls
    assert running.get("game_exit_done") is True


def test_game_adapter_rejects_non_positive_duration() -> None:
    with pytest.raises(ValueError):
        _make_game_adapter(SimulatedDevice(), duration=0.0)


def test_ad_flow_end_to_end_with_real_adapter() -> None:
    observer = PageFlowObserver(
        pages={
            "HOME": home_observation(),
            "REWARD_HOME": reward_observation(),
            "AD_PLAYING": ad_playing_observation(),
            "AD_RESULT": ad_result_observation(),
            "REWARD_DONE": reward_observation(ocr=("12/12",)),
        },
        start="HOME",
        auto_transitions={"AD_PLAYING": ("AD_RESULT", 5.0)},
    )

    def on_tap(name: str) -> None:
        if name == HOME_REWARD_KEY:
            observer.go("REWARD_HOME")
        elif name == REWARD_WATCH_KEY:
            observer.go("AD_PLAYING")
        elif name == AD_SKIP_KEY:
            observer.go("AD_RESULT")
        elif name == AD_RESULT_CLOSE_KEY:
            observer.go("REWARD_DONE")

    device = SimulatedDevice(on_tap_feature=on_tap)
    definition = build_ad_definition(
        KEYS,
        observer,
        device,
        EscalationPolicy(),
        make_recognizer(),
        timeout_seconds=300.0,
    )
    result = TaskRunner(definition, FakeClock()).run()

    assert result.outcome is TaskOutcome.SUCCESS
    assert ("tap_feature", HOME_REWARD_KEY) in device.calls
    assert ("tap_feature", REWARD_WATCH_KEY) in device.calls
    assert ("tap_feature", AD_RESULT_CLOSE_KEY) in device.calls
    assert result.final_state.value == "REWARD_HOME"


def test_game_flow_end_to_end_with_real_adapter() -> None:
    observer = PageFlowObserver(
        pages={
            "HOME": home_observation(),
            "REWARD_HOME": reward_observation(
                # issue #11：进游戏前基线 100（「今日已获赠币100」）。
                ocr=("今日已获赠币100", "玩游戏领赠币", "去玩游戏")
            ),
            "GAME_HALL": game_hall_observation(),
            "GAME_CENTER": game_center_observation(),
            "GAME_AGREEMENT": game_agreement_observation(),
            "GAME_RUNNING": game_running_observation(),
            "GAME_MENU": game_menu_observation(),
            "GAME_EXIT_CONFIRM": game_close_confirm_observation(),
            "REWARD_CLAIM": reward_claim_observation(),
            "REWARD_DONE": reward_done_observation(),
        },
        start="HOME",
    )

    def on_tap(name: str) -> None:
        if name == HOME_REWARD_KEY:
            observer.go("REWARD_HOME")
        elif name == GAME_GO_PLAY_KEY:
            observer.go("GAME_HALL")
        elif name == GAME_ONLINE_PLAY_KEY:
            observer.go(
                "GAME_CENTER" if observer.page == "GAME_HALL" else "GAME_AGREEMENT"
            )
        elif name == GAME_ENTER_KEY:
            observer.go("GAME_RUNNING")
        elif name == GAME_EXIT_MENU_KEY:
            observer.go("GAME_EXIT_CONFIRM")
        elif name == GAME_CLOSE_GAME_KEY:
            observer.go("GAME_HALL")
        elif name == GAME_CLAIM_KEY:
            observer.go("REWARD_DONE")

    def on_tap_point(x: int, y: int) -> None:
        if (x, y) in ((650, 274), (650, 430), (650, 590)):
            observer.go("GAME_AGREEMENT")
        elif (x, y) == (360, 360):
            observer.go("GAME_AGREEMENT")
        elif (x, y) == (695, 302):
            observer.go("GAME_MENU")

    def on_press_back() -> None:
        if observer.page == "GAME_HALL":
            observer.go("REWARD_CLAIM")

    device = SimulatedDevice(
        on_tap_feature=on_tap,
        on_tap_point=on_tap_point,
        on_press_back=on_press_back,
    )
    definition = build_game_definition(
        KEYS,
        observer,
        device,
        EscalationPolicy(),
        make_recognizer(),
        timeout_seconds=300.0,
        game_duration_seconds=30.0,
    )
    result = TaskRunner(definition, FakeClock()).run()

    assert result.outcome is TaskOutcome.SUCCESS
    assert ("tap_feature", HOME_REWARD_KEY) in device.calls
    assert ("swipe", 360, 420, 360, 980, 500) in device.calls
    # issue #12：游戏中心列表页推进 = OCR 定位优先（真机 2026-09-13）。
    # GAME_CENTER 页 OCR 命中「在线玩」→ 直接 tap_feature 进入下一页，
    # 无需坐标兜底（坐标轮换由 test_qqr20 单测覆盖）。
    assert ("tap_feature", GAME_ONLINE_PLAY_KEY) in device.calls
    assert ("tap_point", 98, 981) not in device.calls
    assert ("tap_point", 157, 1032) in device.calls
    assert ("tap_point", 152, 1066) in device.calls
    assert ("tap_feature", GAME_ENTER_KEY) in device.calls
    assert ("tap_point", 695, 302) in device.calls
    assert ("tap_feature", GAME_EXIT_MENU_KEY) in device.calls
    assert ("tap_feature", GAME_CLOSE_GAME_KEY) in device.calls
    assert ("press_back",) in device.calls
    # issue #11 修订：回到奖励页（game_exit_done）当步即判成功，
    # 不再要求「立即领取」点击（该按钮在真实奖励页不存在）。
    kinds = [event.kind for event in result.diagnostics]
    assert "task.success" in kinds
