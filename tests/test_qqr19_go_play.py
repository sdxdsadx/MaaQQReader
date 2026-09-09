"""QQR-19：「去玩游戏」识别/点击失败的回归测试。

覆盖三条路径：

* HOME 使用书架 OCR「本周阅读时长」进入奖励页；
* 奖励页只识别到「玩游戏领赠币」卡片、没识别到「去玩游戏」时，
  使用旧 pipeline 标定的按钮坐标 fallback；
* GAME_ENTRY 状态已确认但 OCR 定位器临时失败时，同样退到坐标 fallback。
"""

from __future__ import annotations

from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.states import PageState, RunState
from qqreader.tasks import Action, ActionKind, GameTaskAdapter, feature_key
from qqreader.tasks.game import build_game_action_plan
from tests.helpers import (
    QQ,
    SimulatedDevice,
    game_entry_observation,
    make_context,
    make_recognizer,
    reward_observation,
)

KEYS = DEFAULT_FEATURE_KEYS
HOME_REWARD_KEY = feature_key(KEYS, KEYS.home_ocr_reward_entry)
GAME_GO_PLAY_KEY = feature_key(KEYS, KEYS.game_ocr_go_play)


def _adapter(device: SimulatedDevice) -> GameTaskAdapter:
    return GameTaskAdapter(
        game_duration_seconds=60.0,
        exit_action=Action.tap_point(695, 302),
        device=device,
        plan=build_game_action_plan(KEYS),
        expected_package=QQ,
        popup_feature=feature_key(KEYS, KEYS.popup_close),
    )


def test_home_action_uses_shelf_reward_ocr_entry() -> None:
    plan = build_game_action_plan(KEYS)
    assert plan.action_for(PageState.HOME).target == HOME_REWARD_KEY
    assert plan.action_for(PageState.HOME).target == "home_ocr_reward_entry"


def test_reward_page_top_is_recognized_by_granted_ocr() -> None:
    # 奖励页顶部只看到「今日已获赠币」时也必须确认 REWARD_HOME，
    # 否则脚本不会滚动查找下方「去玩游戏」。
    decision = make_recognizer().evaluate(
        reward_observation(ocr=("今日已获赠币",))
    )
    assert decision.state is PageState.REWARD_HOME


def test_reward_card_without_go_play_text_uses_button_point() -> None:
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = make_context(
        reward_observation(ocr=("今日已获赠币", "玩游戏领赠币+20赠币")),
        run_state=RunState.RUNNING,
    )
    step = adapter.advance(context)
    assert step.actions == (ActionKind.TAP_POINT.value,)
    assert ("tap_point", 592, 606) in device.calls


def test_game_entry_locator_failure_uses_button_point() -> None:
    device = SimulatedDevice(tap_results={GAME_GO_PLAY_KEY: False})
    adapter = _adapter(device)
    context = make_context(game_entry_observation(), run_state=RunState.RUNNING)
    step = adapter.advance(context)
    assert step.actions == (ActionKind.TAP_POINT.value,)
    assert ("tap_feature", GAME_GO_PLAY_KEY) in device.calls
    assert ("tap_point", 592, 606) in device.calls
