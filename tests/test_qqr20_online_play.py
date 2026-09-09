"""QQR-20：游戏大厅下划一次 → 识别「在线玩」→ 点击进入游戏。"""

from __future__ import annotations

from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.states import PageState, RunState
from qqreader.tasks import Action, ActionKind, GameTaskAdapter, feature_key
from qqreader.tasks.game import build_game_action_plan
from tests.helpers import (
    QQ,
    SimulatedDevice,
    game_center_observation,
    game_hall_observation,
    game_running_observation,
    make_context,
    make_recognizer,
)

KEYS = DEFAULT_FEATURE_KEYS
ONLINE_PLAY_KEY = feature_key(KEYS, KEYS.game_ocr_online_play)
AGREE_KEY = feature_key(KEYS, KEYS.game_ocr_agree)


def _adapter(device: SimulatedDevice) -> GameTaskAdapter:
    return GameTaskAdapter(
        game_duration_seconds=60.0,
        exit_action=Action.tap_point(695, 302),
        device=device,
        plan=build_game_action_plan(KEYS),
        expected_package=QQ,
        popup_feature=feature_key(KEYS, KEYS.popup_close),
    )


def test_game_hall_swipes_once_then_taps_online_play() -> None:
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = make_context(game_hall_observation(), run_state=RunState.RUNNING)

    first = adapter.advance(context)
    assert first.actions == (ActionKind.SWIPE.value,)
    assert context.get("game_hall_swiped") is True

    second = adapter.advance(context)
    assert second.actions == (
        f"{ActionKind.TAP_FEATURE.value}:{ONLINE_PLAY_KEY}",
    )
    assert ("tap_feature", ONLINE_PLAY_KEY) in device.calls


def test_game_hall_locator_failure_falls_back_to_carousel() -> None:
    device = SimulatedDevice(tap_results={ONLINE_PLAY_KEY: False})
    adapter = _adapter(device)
    context = make_context(game_hall_observation(), run_state=RunState.RUNNING)

    adapter.advance(context)  # 下划一次
    step = adapter.advance(context)

    assert step.actions == (ActionKind.TAP_POINT.value,)
    assert ("tap_point", 360, 360) in device.calls


def test_game_hall_after_exit_does_not_swipe_or_click() -> None:
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = make_context(game_hall_observation(), run_state=RunState.RUNNING)
    context.update_data(game_exit_done=True)

    step = adapter.advance(context)

    assert step.actions == (ActionKind.PRESS_BACK.value,)
    assert ("press_back",) in device.calls
    assert ("swipe", 360, 420, 360, 980, 500) not in device.calls


def test_game_running_loading_does_not_start_timer() -> None:
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = make_context(
        game_running_observation(ocr_texts=("领币", "正在连接服务器")),
        run_state=RunState.RUNNING,
    )
    step = adapter.advance(context)
    assert step.actions == ()
    assert step.progress is False
    assert context.get("game_started_at") is None


def test_game_running_agree_popup_clicks_agree() -> None:
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = make_context(
        game_running_observation(ocr_texts=("领币", "同意")),
        run_state=RunState.RUNNING,
    )
    step = adapter.advance(context)
    assert step.actions == (
        f"{ActionKind.TAP_FEATURE.value}:{AGREE_KEY}",
    )
    assert ("tap_feature", AGREE_KEY) in device.calls
    assert context.get("game_agree_clicked") is True


def test_game_center_state() -> None:
    decision = make_recognizer().evaluate(game_center_observation())
    assert decision.state is PageState.GAME_CENTER


def test_game_center_taps_first_card_point_then_cycles() -> None:
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = make_context(game_center_observation(), run_state=RunState.RUNNING)

    first = adapter.advance(context)
    second = adapter.advance(context)

    assert first.actions == (ActionKind.TAP_POINT.value,)
    assert second.actions == (ActionKind.TAP_POINT.value,)
    assert ("tap_point", 98, 981) in device.calls
    assert ("tap_point", 254, 981) in device.calls


def test_exit_done_never_reenters_game() -> None:
    for observation in (
        game_center_observation(),
        game_running_observation(),
    ):
        device = SimulatedDevice()
        adapter = _adapter(device)
        context = make_context(observation, run_state=RunState.RUNNING)
        context.update_data(game_exit_done=True)

        step = adapter.advance(context)

        assert step.actions == (ActionKind.PRESS_BACK.value,)
        assert ("press_back",) in device.calls
        assert ("tap_feature", ONLINE_PLAY_KEY) not in device.calls
