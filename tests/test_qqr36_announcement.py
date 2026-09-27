"""QQR-36：游戏更新公告弹窗——按用户口径作为挂机落地页计时。"""

from __future__ import annotations

from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.observation import PageObservation
from qqreader.page.states import Orientation, PageState, RunState
from qqreader.tasks import Action, GameTaskAdapter, feature_key
from qqreader.tasks.game import build_game_action_plan, build_game_contract
from tests.helpers import QQ, SimulatedDevice, make_context, make_recognizer

KEYS = DEFAULT_FEATURE_KEYS

#: 真机 2026-09-11 抓到的公告弹窗文案（标题 / 正文小节 / 正文片段）。
ANNOUNCEMENT_TEXTS = ("亲爱的仙使大人：", "一、全新功能", "适齿")


def announcement_observation(*extra_texts: str) -> PageObservation:
    return PageObservation(
        current_app=QQ,
        orientation=Orientation.PORTRAIT,
        ocr_texts=ANNOUNCEMENT_TEXTS + extra_texts,
    )


def _adapter() -> tuple[GameTaskAdapter, SimulatedDevice]:
    device = SimulatedDevice()
    adapter = GameTaskAdapter(
        game_duration_seconds=60.0,
        exit_action=Action.tap_point(695, 302),
        device=device,
        plan=build_game_action_plan(KEYS),
        expected_package=KEYS.qq_reader_package,
        popup_feature=feature_key(KEYS, KEYS.popup_close),
    )
    return adapter, device


def test_announcement_state_recognized() -> None:
    decision = make_recognizer().evaluate(announcement_observation())
    assert decision.state is PageState.GAME_ANNOUNCEMENT
    # 公告弹窗没有「领币」悬浮窗证据，同一观测不得判成 GAME_RUNNING。
    running = decision.candidate(PageState.GAME_RUNNING)
    assert running is not None and running.confirmed is False


def test_announcement_in_progress_condition() -> None:
    contract = build_game_contract(KEYS)
    context = make_context(
        announcement_observation(), contract=contract, run_state=RunState.RUNNING
    )
    assert context.state is PageState.GAME_ANNOUNCEMENT

    result = contract.progress_condition.evaluate(context)

    assert result.satisfied is True


def test_announcement_starts_game_timer() -> None:
    adapter, device = _adapter()
    context = make_context(announcement_observation(), run_state=RunState.RUNNING)
    assert context.state is PageState.GAME_ANNOUNCEMENT

    step = adapter.advance(context)

    assert step.description == "确认游戏公告/登录落地页，开始挂机计时"
    assert step.actions == ("GAME_TIMER_START",)
    assert context.get("game_started_at") == context.now
    assert device.calls == []


def test_announcement_exits_after_timer_even_when_skip_is_visible() -> None:
    adapter, device = _adapter()
    context = make_context(
        announcement_observation("跳过"), run_state=RunState.RUNNING
    )
    assert context.state is PageState.GAME_ANNOUNCEMENT
    context.update_data(game_started_at=context.now - 61.0)

    step = adapter.advance(context)

    assert any("PRESS_BACK" in str(action) for action in step.actions)
    assert context.get("game_exit_done") is True
    assert ("press_back",) in device.calls


def test_announcement_title_overrides_false_loading_match() -> None:
    adapter, device = _adapter()
    observation = PageObservation(
        current_app=None,
        orientation=Orientation.PORTRAIT,
        ocr_texts=(
            "亲爱的仙使大人：",
            "间无法进入游戏，不便之处，敬请谅解！",
            "领币",
        ),
    )
    context = make_context(observation, run_state=RunState.RUNNING)
    assert context.state is PageState.GAME_LOADING

    step = adapter.advance(context)

    assert step.description == "确认游戏公告/登录落地页，开始挂机计时"
    assert step.actions == ("GAME_TIMER_START",)
    assert device.calls == []


def test_open_server_announcement_is_a_valid_hang_page() -> None:
    observation = PageObservation(
        current_app=None,
        orientation=Orientation.PORTRAIT,
        ocr_texts=("版本号：1.7.1118744", "开服公告", "亲爱的各位玩家："),
    )
    context = make_context(observation, run_state=RunState.RUNNING)
    assert context.state is PageState.GAME_ANNOUNCEMENT
    adapter, device = _adapter()

    step = adapter.advance(context)

    assert step.actions == ("GAME_TIMER_START",)
    assert device.calls == []
