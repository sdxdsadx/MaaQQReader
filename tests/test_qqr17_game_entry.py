"""QQR-17：奖励页「玩游戏领赠币」入口与「去玩游戏」按钮。

锁定实际失败链路：

* 奖励页 OCR「玩游戏领赠币」必须能确认 REWARD_HOME；
* 点击后出现「去玩游戏」的中间页必须确认新的 GAME_ENTRY 状态；
* 游戏动作计划必须用 OCR 特征点击这两个入口，而不是只依赖未标定的模板。
"""

from __future__ import annotations

from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.states import PageState, RunState
from qqreader.tasks import Action, ActionKind, GameTaskAdapter, feature_key
from qqreader.tasks.game import build_game_action_plan, build_game_contract
from tests.helpers import (
    SimulatedDevice,
    game_entry_observation,
    game_hall_observation,
    make_context,
    make_recognizer,
    reward_observation,
)

KEYS = DEFAULT_FEATURE_KEYS

HOME_REWARD_KEY = feature_key(KEYS, KEYS.home_reward_entry)
GAME_REWARD_ENTRY_KEY = feature_key(KEYS, KEYS.game_ocr_reward_entry)
GAME_GO_PLAY_KEY = feature_key(KEYS, KEYS.game_ocr_go_play)
GAME_ENTER_KEY = feature_key(KEYS, KEYS.game_ocr_enter)
GAME_EXIT_MENU_KEY = feature_key(KEYS, KEYS.game_exit_menu)
POPUP_CLOSE_KEY = feature_key(KEYS, KEYS.popup_close)


def test_reward_page_game_banner_is_reward_home() -> None:
    decision = make_recognizer().evaluate(
        reward_observation(ocr=("今日已获赠币", "玩游戏领赠币"))
    )
    assert decision.state is PageState.REWARD_HOME


def test_go_play_button_is_game_entry_state() -> None:
    decision = make_recognizer().evaluate(game_entry_observation())
    assert decision.state is PageState.GAME_ENTRY
    candidate = decision.candidate(PageState.GAME_ENTRY)
    assert candidate is not None
    assert candidate.confirmed is True


def test_game_entry_state_requires_go_play_ocr() -> None:
    # 只有奖励页文案、没有「去玩游戏」时，不能误判为 GAME_ENTRY。
    decision = make_recognizer().evaluate(
        reward_observation(ocr=("今日已获赠币", "玩游戏领赠币"))
    )
    assert decision.state is not PageState.GAME_ENTRY


def test_feature_key_resolves_ocr_text_to_adapter_field_name() -> None:
    # MaaFeatureLocator 只认 FeatureCatalog 的字段名；不能把 OCR 文案直接当 target。
    assert GAME_GO_PLAY_KEY == "game_ocr_go_play"
    assert GAME_GO_PLAY_KEY != KEYS.game_ocr_go_play
    assert GAME_REWARD_ENTRY_KEY in ("reward_ocr_game_banner", "game_ocr_reward_entry")
    assert GAME_REWARD_ENTRY_KEY != KEYS.game_ocr_reward_entry


def test_game_action_plan_uses_ocr_for_both_entries() -> None:
    plan = build_game_action_plan(KEYS)
    assert plan.action_for(PageState.HOME).target == HOME_REWARD_KEY
    assert plan.action_for(PageState.REWARD_HOME).target == GAME_GO_PLAY_KEY
    assert plan.action_for(PageState.GAME_ENTRY).target == GAME_GO_PLAY_KEY
    assert plan.action_for(PageState.GAME_LOADING).target == GAME_ENTER_KEY


def _make_entry_adapter(device: SimulatedDevice) -> GameTaskAdapter:
    return GameTaskAdapter(
        game_duration_seconds=60.0,
        exit_action=Action.tap_feature(GAME_EXIT_MENU_KEY),
        device=device,
        plan=build_game_action_plan(KEYS),
        expected_package=KEYS.qq_reader_package,
        popup_feature=POPUP_CLOSE_KEY,
        reward_entry_key=GAME_REWARD_ENTRY_KEY,
        go_play_key=GAME_GO_PLAY_KEY,
        reward_entry_text=KEYS.game_ocr_reward_entry,
        go_play_text=KEYS.game_ocr_go_play,
        entry_scroll_action=Action.swipe(360, 980, 360, 420, 500),
    )


def test_reward_page_with_go_play_button_taps_button() -> None:
    device = SimulatedDevice()
    adapter = _make_entry_adapter(device)
    context = make_context(
        reward_observation(ocr=("今日已获赠币", "玩游戏领赠币", "去玩游戏")),
        run_state=RunState.RUNNING,
    )
    step = adapter.advance(context)
    assert step.actions == (f"{ActionKind.TAP_FEATURE.value}:{GAME_GO_PLAY_KEY}",)
    assert ("tap_feature", GAME_GO_PLAY_KEY) in device.calls


def test_reward_page_with_game_card_only_taps_reward_card() -> None:
    device = SimulatedDevice()
    adapter = _make_entry_adapter(device)
    context = make_context(
        reward_observation(ocr=("今日已获赠币", "玩游戏领赠币")),
        run_state=RunState.RUNNING,
    )
    step = adapter.advance(context)
    assert step.actions == (
        f"{ActionKind.TAP_FEATURE.value}:{GAME_REWARD_ENTRY_KEY}",
    )
    assert ("tap_feature", GAME_REWARD_ENTRY_KEY) in device.calls


def test_reward_page_without_entry_scrolls_before_retry() -> None:
    device = SimulatedDevice()
    adapter = _make_entry_adapter(device)
    context = make_context(
        reward_observation(ocr=("今日已获赠币",)),
        run_state=RunState.RUNNING,
    )
    step = adapter.advance(context)
    assert step.actions == (ActionKind.SWIPE.value,)
    assert device.calls[0][0] == "swipe"
    assert context.get("game_entry_scrolls") == 1


def test_game_entry_page_taps_go_play_button() -> None:
    device = SimulatedDevice()
    adapter = _make_entry_adapter(device)
    context = make_context(game_entry_observation(), run_state=RunState.RUNNING)
    step = adapter.advance(context)
    assert step.actions == (f"{ActionKind.TAP_FEATURE.value}:{GAME_GO_PLAY_KEY}",)
    assert ("tap_feature", GAME_GO_PLAY_KEY) in device.calls


def test_game_hall_is_recognized_as_game_hall() -> None:
    decision = make_recognizer().evaluate(game_hall_observation())
    assert decision.state is PageState.GAME_HALL


def test_game_contract_has_game_entry_intermediate_state() -> None:
    contract = build_game_contract(KEYS)
    assert "GAME_ENTRY" in contract.start_condition.describe()
    assert "GAME_ENTRY" in contract.ready_condition.describe()
    assert "GAME_ENTRY" in contract.progress_condition.describe()
