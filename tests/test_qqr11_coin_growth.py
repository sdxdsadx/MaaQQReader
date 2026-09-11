"""issue #11（修订）：游戏 daily 成功判定 = 流程闭环，赠币计数仅作遥测。

真实奖励页不存在「玩游戏领赠币+已领取」文案；且 r36/r37 两轮全链路实测
「在线玩」游戏流程不发放 QQ阅读赠币（「今日已获赠币」恒为 100，+70 卡是
「充值领赠币」任务）——赠币增长语义不成立。最终成功语义：进游戏→挂机
计时→自动退出→回到奖励页（game_exit_done），流程闭环即 success；
``GameCoinGrew`` 保留为可选遥测条件，不再作门禁。
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


def test_success_condition_on_flow_completion() -> None:
    """game_exit_done + 回到 REWARD_HOME：流程闭环 → 成功（赠币仅遥测）。"""
    observation = reward_observation(ocr=("今日已获赠币120", "去玩游戏", "获奖记录"))
    context = make_context(
        observation, contract=_contract(), run_state=RunState.RUNNING
    )
    assert context.decision.state is PageState.REWARD_HOME
    # 赠币未增长（100 → 100）也不影响：遥测仅作 evidence。
    context.update_data(
        game_exit_done=True, game_coin_baseline=100, game_coin_after=100
    )

    result = _contract().success_condition.evaluate(context)

    assert result.satisfied is True
    # AllOf 聚合 evidence：game_flow_completed 子条件为满足。
    assert result.evidence.get("game_flow_completed") is True


def test_success_condition_not_satisfied_before_exit_done() -> None:
    """未退出 / 未回到奖励页：两种情形都不满足成功条件。"""
    observation = reward_observation(ocr=("今日已获赠币100", "去玩游戏", "获奖记录"))

    # 游戏尚未退出（game_exit_done 缺失）。
    context = make_context(
        observation, contract=_contract(), run_state=RunState.RUNNING
    )
    result = _contract().success_condition.evaluate(context)
    assert result.satisfied is False
    assert "退出" in result.reason

    # 退出但未捕获赠币数值：仍应成功（数值只是遥测，不是门禁）。
    context_exit = make_context(
        observation, contract=_contract(), run_state=RunState.RUNNING
    )
    context_exit.update_data(game_exit_done=True)
    assert _contract().success_condition.evaluate(context_exit).satisfied is True


def test_other_card_mingri_zailai_never_satisfies_success() -> None:
    """他卡（百度地图）页「明日再来」不构成成功证据；退出前判定永不满足。"""
    observation = reward_observation(
        ocr=("玩游戏领赠币", "明日再来", "今日已获赠币100")
    )
    context = make_context(
        observation, contract=_contract(), run_state=RunState.RUNNING
    )
    assert context.decision.state is PageState.REWARD_HOME
    context.update_data(game_coin_baseline=100)
    # 「明日再来」等他卡文案不是成功条件的一部分；未退出 → 不满足。
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
    # 流程已闭环（game_exit_done + REWARD_HOME）→ 成功条件满足。
    assert _contract().success_condition.evaluate(context).satisfied is True


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
