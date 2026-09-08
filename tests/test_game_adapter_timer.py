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
)
from tests.helpers import (
    QQ,
    PageFlowObserver,
    SimulatedDevice,
    ad_playing_observation,
    ad_result_observation,
    game_loading_observation,
    game_running_observation,
    home_observation,
    make_context,
    make_recognizer,
    reward_done_observation,
    reward_observation,
)

KEYS = DEFAULT_FEATURE_KEYS


def _make_game_adapter(device, duration: float) -> GameTaskAdapter:
    return GameTaskAdapter(
        game_duration_seconds=duration,
        exit_action=Action.tap_feature(KEYS.game_exit_menu),
        device=device,
        plan=build_game_action_plan(KEYS),
        expected_package=QQ,
        popup_feature=KEYS.popup_close,
    )


def test_game_timer_starts_only_after_running_and_exits_after_duration() -> None:
    clock = FakeClock()
    device = SimulatedDevice()
    adapter = _make_game_adapter(device, duration=60.0)
    contract = build_game_contract(KEYS)

    loading = make_context(
        game_loading_observation(), contract=contract, clock=clock, run_state=RunState.RUNNING
    )
    adapter.advance(loading)
    assert loading.get("game_started_at") is None
    assert device.calls == [("tap_feature", KEYS.game_ocr_enter_alt)]

    running = make_context(
        game_running_observation(), contract=contract, clock=clock, run_state=RunState.RUNNING
    )
    first = adapter.advance(running)
    assert first.actions == ("GAME_TIMER_START",)
    assert running.get("game_started_at") == 0.0

    waiting = adapter.advance(running)
    assert waiting.actions == (ActionKind.WAIT.value,)
    assert clock.now() == 10.0
    assert ("tap_feature", KEYS.game_exit_menu) not in device.calls

    clock.advance(50.0)  # 累计 60s，达到挂机时长
    exiting = adapter.advance(running)
    assert exiting.actions == (f"{ActionKind.TAP_FEATURE.value}:{KEYS.game_exit_menu}",)
    assert ("tap_feature", KEYS.game_exit_menu) in device.calls


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
        if name == KEYS.home_reward_entry:
            observer.go("REWARD_HOME")
        elif name == KEYS.reward_ocr_watch:
            observer.go("AD_PLAYING")
        elif name == KEYS.ad_result_close:
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
    assert ("tap_feature", KEYS.home_reward_entry) in device.calls
    assert ("tap_feature", KEYS.reward_ocr_watch) in device.calls
    assert ("tap_feature", KEYS.ad_result_close) in device.calls
    assert result.final_state.value == "REWARD_HOME"


def test_game_flow_end_to_end_with_real_adapter() -> None:
    observer = PageFlowObserver(
        pages={
            "HOME": home_observation(),
            "REWARD_HOME": reward_observation(),
            "GAME_LOADING": game_loading_observation(),
            "GAME_RUNNING": game_running_observation(),
            "REWARD_DONE": reward_done_observation(),
        },
        start="HOME",
    )

    def on_tap(name: str) -> None:
        if name == KEYS.game_entry:
            observer.go(
                "GAME_LOADING" if observer.page == "REWARD_HOME" else "REWARD_HOME"
            )
        elif name == KEYS.game_ocr_enter_alt:
            observer.go("GAME_RUNNING")
        elif name == KEYS.game_exit_menu:
            observer.go("REWARD_DONE")

    device = SimulatedDevice(on_tap_feature=on_tap)
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
    assert ("tap_feature", KEYS.game_entry) in device.calls
    assert ("tap_feature", KEYS.game_ocr_enter_alt) in device.calls
    assert ("tap_feature", KEYS.game_exit_menu) in device.calls
    kinds = [event.kind for event in result.diagnostics]
    assert "task.success" in kinds
