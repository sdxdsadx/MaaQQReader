"""QQR-18：游戏大厅 → 进入游戏 → 领币悬浮窗 → 退出/关闭 → 奖励页领取。

本文件锁定新状态与默认 22 分钟计时；完整点击链路由
``test_game_adapter_timer.test_game_flow_end_to_end_with_real_adapter`` 覆盖。
"""

from __future__ import annotations

from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.observation import PageObservation
from qqreader.page.states import Orientation, PageState, RunState
from qqreader.tasks import Action, ActionKind, GameTaskAdapter, feature_key
from qqreader.tasks.game import (
    DEFAULT_GAME_DURATION_SECONDS,
    build_game_action_plan,
    build_game_contract,
)
from tests.helpers import (
    QQ,
    SimulatedDevice,
    game_agreement_observation,
    game_close_confirm_observation,
    game_hall_observation,
    game_menu_observation,
    game_running_observation,
    make_context,
    make_recognizer,
    reward_claim_observation,
)

KEYS = DEFAULT_FEATURE_KEYS


def test_game_hall_state() -> None:
    decision = make_recognizer().evaluate(game_hall_observation())
    assert decision.state is PageState.GAME_HALL


def test_game_agreement_state_is_loading() -> None:
    decision = make_recognizer().evaluate(game_agreement_observation())
    assert decision.state is PageState.GAME_LOADING


def test_game_running_state() -> None:
    decision = make_recognizer().evaluate(game_running_observation())
    assert decision.state is PageState.GAME_RUNNING


def test_game_menu_state() -> None:
    decision = make_recognizer().evaluate(game_menu_observation())
    assert decision.state is PageState.GAME_MENU


def test_game_exit_confirm_state() -> None:
    decision = make_recognizer().evaluate(game_close_confirm_observation())
    assert decision.state is PageState.GAME_EXIT_CONFIRM


def test_reward_claim_page_is_reward_home() -> None:
    decision = make_recognizer().evaluate(reward_claim_observation())
    assert decision.state is PageState.REWARD_HOME


def test_default_game_duration_is_22_minutes() -> None:
    assert DEFAULT_GAME_DURATION_SECONDS == 22 * 60


def test_game_contract_includes_new_states() -> None:
    contract = build_game_contract(KEYS)
    for name in ("GAME_HALL", "GAME_MENU", "GAME_EXIT_CONFIRM"):
        assert name in contract.ready_condition.describe() or name in (
            contract.progress_condition.describe()
        )


def test_game_entry_after_exit_claims_instead_of_reentering() -> None:
    """奖励页游戏区可能被判成 GAME_ENTRY；退出后必须领币，不能再次进游戏。"""
    device = SimulatedDevice()
    adapter = GameTaskAdapter(
        game_duration_seconds=60.0,
        exit_action=Action.tap_point(695, 302),
        device=device,
        plan=build_game_action_plan(KEYS),
        expected_package=KEYS.qq_reader_package,
        popup_feature=feature_key(KEYS, KEYS.popup_close),
    )
    observation = PageObservation(
        current_app=QQ,
        orientation=Orientation.PORTRAIT,
        ocr_texts=(
            "今日已获赠币",
            "玩游戏领赠币+20赠币",
            "去玩游戏",
            "立即领取",
        ),
    )
    context = make_context(observation, run_state=RunState.RUNNING)
    assert context.state is PageState.GAME_ENTRY
    context.update_data(game_exit_done=True)

    step = adapter.advance(context)

    claim_key = feature_key(KEYS, KEYS.game_ocr_claim)
    assert step.actions == (f"{ActionKind.TAP_FEATURE.value}:{claim_key}",)
    assert ("tap_feature", claim_key) in device.calls
