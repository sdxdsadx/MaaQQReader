"""QQR-36：游戏更新公告弹窗——识别、进度条件与关闭动作（返回/跳过）。"""

from __future__ import annotations

from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.observation import PageObservation
from qqreader.page.states import Orientation, PageState, RunState
from qqreader.tasks import Action, ActionKind, GameTaskAdapter, feature_key
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


def test_announcement_dismiss_without_skip() -> None:
    """OCR 未命中「跳过」时按返回键关闭公告（game_exit_done 未设置）。"""
    adapter, device = _adapter()
    context = make_context(announcement_observation(), run_state=RunState.RUNNING)
    assert context.state is PageState.GAME_ANNOUNCEMENT

    step = adapter.advance(context)

    assert any("PRESS_BACK" in str(action) for action in step.actions)
    assert ("press_back",) in device.calls


def test_announcement_dismiss_with_skip() -> None:
    """OCR 命中「跳过」时点击跳过特征，而不是按返回键。"""
    adapter, device = _adapter()
    context = make_context(
        announcement_observation("跳过"), run_state=RunState.RUNNING
    )
    assert context.state is PageState.GAME_ANNOUNCEMENT

    step = adapter.advance(context)

    skip_key = feature_key(KEYS, KEYS.game_ocr_announcement_skip)
    assert "skip" in skip_key
    assert step.actions == (f"{ActionKind.TAP_FEATURE.value}:{skip_key}",)
    assert ("tap_feature", skip_key) in device.calls
    assert ("press_back",) not in device.calls
