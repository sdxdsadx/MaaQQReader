"""issue #11：领取成功判定锚定「今日已获赠币」数值增长。

旧判定依赖「玩游戏领赠币+已领取」文案组合，真实奖励页不存在该文案；
新判定 = REWARD_HOME 状态 + 赠币计数较进游戏前基线增长（数值由
``GameTaskAdapter`` 捕获入 ``context.data``，条件只做纯比较）。
"""

from __future__ import annotations

from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.states import PageState, RunState
from qqreader.tasks import Action, ActionKind, GameTaskAdapter, feature_key
from qqreader.tasks.game import build_game_action_plan, build_game_contract
from tests.helpers import QQ, SimulatedDevice, make_context, reward_observation

KEYS = DEFAULT_FEATURE_KEYS


def _contract():
    return build_game_contract(KEYS)


def _coin_adapter() -> tuple[GameTaskAdapter, SimulatedDevice]:
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


def test_success_condition_on_coin_growth() -> None:
    """基线 100 → 现值 120：REWARD_HOME + 数值增长 → 成功。"""
    observation = reward_observation(ocr=("今日已获赠币120", "去玩游戏", "获奖记录"))
    context = make_context(
        observation, contract=_contract(), run_state=RunState.RUNNING
    )
    assert context.decision.state is PageState.REWARD_HOME
    context.update_data(game_coin_baseline=100, game_coin_after=120)

    result = _contract().success_condition.evaluate(context)

    assert result.satisfied is True


def test_success_condition_not_satisfied_without_growth() -> None:
    """未增长 / 缺现值 / 缺基线：三种情形都不满足成功条件。"""
    observation = reward_observation(ocr=("今日已获赠币100", "去玩游戏", "获奖记录"))

    # 数值未增长（100 → 100）。
    context = make_context(
        observation, contract=_contract(), run_state=RunState.RUNNING
    )
    context.update_data(game_coin_baseline=100, game_coin_after=100)
    result = _contract().success_condition.evaluate(context)
    assert result.satisfied is False
    assert "未增长" in result.reason

    # 缺现值（游戏未退出/未读到计数器）。
    context_missing_after = make_context(
        observation, contract=_contract(), run_state=RunState.RUNNING
    )
    context_missing_after.update_data(game_coin_baseline=100)
    assert _contract().success_condition.evaluate(context_missing_after).satisfied is False

    # 缺基线（进游戏前没读到「今日已获赠币N」）。
    context_missing_baseline = make_context(
        observation, contract=_contract(), run_state=RunState.RUNNING
    )
    context_missing_baseline.update_data(game_coin_after=120)
    assert (
        _contract().success_condition.evaluate(context_missing_baseline).satisfied
        is False
    )


def test_other_card_mingri_zailai_never_satisfies_success() -> None:
    """他卡（百度地图）页「明日再来」+ 无增长证据：绝不判成功，也绝不点击。"""
    observation = reward_observation(
        ocr=("玩游戏领赠币", "明日再来", "今日已获赠币100")
    )
    context = make_context(
        observation, contract=_contract(), run_state=RunState.RUNNING
    )
    assert context.decision.state is PageState.REWARD_HOME
    context.update_data(game_coin_baseline=100)
    # 只有基线、无现值/无增长 → 成功条件不满足。
    assert _contract().success_condition.evaluate(context).satisfied is False

    adapter, device = _coin_adapter()
    context.update_data(game_exit_done=True)
    for _ in range(5):
        step = adapter.advance(context)
        # 不产生任何 tap（tap_feature/tap_point 都不允许）——只能滚动或等待。
        assert all(
            not action.startswith(ActionKind.TAP_FEATURE.value)
            and not action.startswith(ActionKind.TAP_POINT.value)
            for action in step.actions
        )
    # 滚动预算用尽后回到等待语义。
    assert step.actions == ()
    assert step.progress is False
    assert not any(call[0] in ("tap_feature", "tap_point") for call in device.calls)
    # 数值 100 → 100 未增长，成功条件仍不满足。
    assert _contract().success_condition.evaluate(context).satisfied is False


def test_success_without_claim_button() -> None:
    """无「立即领取」按钮时，数值增长即可判定领取成功（不点「去玩游戏」）。"""
    adapter, device = _coin_adapter()
    observation = reward_observation(
        ocr=("今日已获赠币120", "去玩游戏", "获奖记录")
    )
    context = make_context(
        observation, contract=_contract(), run_state=RunState.RUNNING
    )
    context.update_data(game_exit_done=True, game_coin_baseline=100)

    step = adapter.advance(context)

    assert step.progress is True
    assert step.actions == ()
    assert "领取成功" in step.description
    assert context.get("game_coin_after") == 120
    # 绝不点「去玩游戏」fallback 坐标，也不做任何点击。
    assert ("tap_point", 592, 606) not in device.calls
    assert not any(call[0] in ("tap_feature", "tap_point") for call in device.calls)
    # 退出后回到 REWARD_HOME：此时成功条件整体满足。
    assert _contract().success_condition.evaluate(context).satisfied is True


def test_baseline_captured_on_first_reward_home() -> None:
    """首次 REWARD_HOME 观测捕获基线；同页再次 advance 不改写基线。"""
    adapter, device = _coin_adapter()
    observation = reward_observation(ocr=("今日已获赠币100", "去玩游戏"))
    context = make_context(
        observation, contract=_contract(), run_state=RunState.RUNNING
    )
    assert context.decision.state is PageState.REWARD_HOME

    adapter.advance(context)

    assert context.get("game_coin_baseline") == 100

    # 基线已存在时不得重复捕获/改写（即使页面数值后来变化）。
    context.update_data(game_coin_baseline=999)
    adapter.advance(context)
    assert context.get("game_coin_baseline") == 999
    assert ("tap_feature", feature_key(KEYS, KEYS.game_ocr_go_play)) in device.calls


def test_exit_done_still_taps_claim_when_visible() -> None:
    """回归保护（QQR-36）：退出后「立即领取」可见仍直接点，原行为保留。"""
    adapter, device = _coin_adapter()
    observation = reward_observation(
        ocr=("今日已获赠币", "玩游戏领赠币+20赠币", "立即领取")
    )
    context = make_context(
        observation, contract=_contract(), run_state=RunState.RUNNING
    )
    context.update_data(game_exit_done=True)  # 无基线/无增长证据

    step = adapter.advance(context)

    claim_key = feature_key(KEYS, KEYS.game_ocr_claim)
    assert step.actions == (f"{ActionKind.TAP_FEATURE.value}:{claim_key}",)
    assert ("tap_feature", claim_key) in device.calls
