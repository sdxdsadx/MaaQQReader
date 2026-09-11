"""issue #13：游戏协议模态框（请先同意→确定）与勾选闭环的状态机推进。"""

from __future__ import annotations

from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.observation import PageObservation
from qqreader.page.states import Orientation, PageState, RunState
from qqreader.tasks import Action, ActionKind, GameTaskAdapter, feature_key
from qqreader.tasks.game import build_game_action_plan
from tests.helpers import QQ, SimulatedDevice, make_context, make_recognizer

KEYS = DEFAULT_FEATURE_KEYS
CONFIRM_KEY = feature_key(KEYS, KEYS.game_ocr_confirm)
ENTER_KEY = feature_key(KEYS, KEYS.game_ocr_enter)


def modal_observation() -> PageObservation:
    """新区游戏：点「进入游戏」后弹出的协议模态框（底层页面文案仍被 OCR 读到）。"""
    return PageObservation(
        current_app=QQ,
        orientation=Orientation.PORTRAIT,
        ocr_texts=(
            "请先同意用户协议和隐私政策！",
            "确定",
            "我已详细阅读并同意",
            "进入游戏",
        ),
    )


def agreement_page_observation() -> PageObservation:
    """模态框消失后：勾选行 + 进入游戏（新区游戏布局）。"""
    return PageObservation(
        current_app=QQ,
        orientation=Orientation.PORTRAIT,
        ocr_texts=("我已详细阅读并同意", "进入游戏"),
    )


def enter_page_observation() -> PageObservation:
    return PageObservation(
        current_app=QQ,
        orientation=Orientation.PORTRAIT,
        ocr_texts=("进入游戏",),
    )


def modal_garbled_observation() -> PageObservation:
    """r40 实测：模态框正文被 OCR 压字（读成「-42」），仅「确定」可读。

    「确定」与「进入游戏」同屏 → 组合信号仍必须触发模态框处理。
    """
    return PageObservation(
        current_app=QQ,
        orientation=Orientation.PORTRAIT,
        ocr_texts=(
            "提示",
            "-42",
            "确定",
            "梦幻2服",
            "进入游戏",
            "我已详细阅读并同意",
        ),
    )


def _adapter_and_device() -> tuple[GameTaskAdapter, SimulatedDevice]:
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


def _observe(context, observation: PageObservation) -> None:
    context.update_observation(observation, make_recognizer().evaluate(observation))


def test_modal_confirm_taps_determine() -> None:
    """模态框出现：优先点「确定」，绝不点勾选行/进入游戏。"""
    adapter, device = _adapter_and_device()
    context = make_context(modal_observation(), run_state=RunState.RUNNING)
    assert context.state is PageState.GAME_LOADING

    step = adapter.advance(context)

    assert step.actions == (f"{ActionKind.TAP_FEATURE.value}:{CONFIRM_KEY}",)
    assert ("tap_feature", CONFIRM_KEY) in device.calls
    assert context.get("game_confirm_clicks") == 1
    assert ("tap_point", 157, 1032) not in device.calls
    assert ("tap_feature", ENTER_KEY) not in device.calls


def test_modal_confirm_clicks_capped_no_deadloop() -> None:
    """同一模态框观测反复 advance：确定最多点 3 次，之后置阻断标志等 fatal。"""
    adapter, device = _adapter_and_device()
    context = make_context(modal_observation(), run_state=RunState.RUNNING)

    for _ in range(5):
        adapter.advance(context)

    confirm_calls = [c for c in device.calls if c == ("tap_feature", CONFIRM_KEY)]
    # 5 次 advance 循环语义：3 次确定 → back 换卡（重置配额）→ 第 4 次确定。
    assert len(confirm_calls) == 4
    assert ("press_back",) in device.calls
    assert context.get("game_confirm_clicks") == 1
    # 「进入游戏」永远不许在模态框观测下点击——防死循环关键。
    assert ("tap_feature", ENTER_KEY) not in device.calls
    assert ("tap_point", 157, 1032) not in device.calls
    # 尚有卡可换（game_center_attempts 未试尽）→ 不置阻断标志。
    assert context.get("game_enter_blocked") is None


def test_modal_then_agreement_then_enter_sequence() -> None:
    """闭环：点确定 → 勾选行点两坐标 → 点进入游戏 → 弹窗复现再点确定。"""
    adapter, device = _adapter_and_device()
    context = make_context(modal_observation(), run_state=RunState.RUNNING)

    step1 = adapter.advance(context)
    assert step1.actions == (f"{ActionKind.TAP_FEATURE.value}:{CONFIRM_KEY}",)

    _observe(context, agreement_page_observation())
    adapter.advance(context)
    assert ("tap_point", 157, 1032) in device.calls

    _observe(context, agreement_page_observation())
    adapter.advance(context)
    assert ("tap_point", 152, 1066) in device.calls

    _observe(context, enter_page_observation())
    step4 = adapter.advance(context)
    assert ("tap_feature", ENTER_KEY) in device.calls
    assert "进入游戏" in step4.description or ENTER_KEY in str(step4.actions)

    # 弹窗复现（确定点击未生效/再次触发协议）：复核后继续点确定，且受次数上限约束。
    _observe(context, modal_observation())
    step5 = adapter.advance(context)
    assert step5.actions == (f"{ActionKind.TAP_FEATURE.value}:{CONFIRM_KEY}",)
    confirm_calls = [c for c in device.calls if c == ("tap_feature", CONFIRM_KEY)]
    assert len(confirm_calls) == 2


def test_agreement_page_without_modal_keeps_legacy_behavior() -> None:
    """无模态框（旧游戏）：不点确定，仍按勾选两坐标各一次 → 进入游戏。"""
    adapter, device = _adapter_and_device()
    context = make_context(agreement_page_observation(), run_state=RunState.RUNNING)
    assert context.state is PageState.GAME_LOADING

    adapter.advance(context)
    assert ("tap_point", 157, 1032) in device.calls
    assert ("tap_feature", CONFIRM_KEY) not in device.calls

    _observe(context, agreement_page_observation())
    adapter.advance(context)
    assert ("tap_point", 152, 1066) in device.calls

    _observe(context, enter_page_observation())
    adapter.advance(context)
    assert ("tap_feature", ENTER_KEY) in device.calls
    assert ("tap_feature", CONFIRM_KEY) not in device.calls


def test_modal_garbled_text_still_triggers_via_confirm_enter_combo() -> None:
    """r40 回归：正文压字读不出「请先同意」时，「确定」+「进入游戏」同屏
    组合信号必须触发点确定，否则继续 693 步死循环。"""
    adapter, device = _adapter_and_device()
    context = make_context(modal_garbled_observation(), run_state=RunState.RUNNING)
    assert context.state is PageState.GAME_LOADING

    step = adapter.advance(context)

    assert step.actions == (f"{ActionKind.TAP_FEATURE.value}:{CONFIRM_KEY}",)
    assert ("tap_feature", CONFIRM_KEY) in device.calls
    assert ("tap_feature", ENTER_KEY) not in device.calls
    assert context.get("game_confirm_clicks") == 1


def test_enter_blocked_fatal_rule_fires() -> None:
    """r41 回归（修订）：确定配额耗尽 → 先换卡（back）轮换；全部卡试尽后
    game_enter_blocked → fatal 规则命中（快速 FAILED，不空转 40 分钟）。"""
    from qqreader.tasks.common import health_fatal_errors

    adapter, device = _adapter_and_device()
    context = make_context(modal_observation(), run_state=RunState.RUNNING)
    # 3 次确定耗尽 → back 换卡 ×4（game_center_attempts 0→4）→ 全部试尽置标志。
    # 每轮观测不变（模拟一直坏卡），模态框观测会被判 GAME_LOADING，
    # back 后 GAME_CENTER 分支只在状态为 GAME_CENTER 时轮换——这里直接
    # 模拟「回到 GAME_CENTER」的观测驱动换卡逻辑。
    for _ in range(4):
        adapter.advance(context)  # 3 次确定 + 第 4 次触发 back 换卡（重置配额）
    assert context.get("game_enter_blocked") is None
    assert ("press_back",) in device.calls

    # 模拟全部卡试尽（game_center_attempts 达 4）：再耗尽一轮确定后置标志。
    context.update_data(game_center_attempts=4)
    for _ in range(4):
        adapter.advance(context)  # 3 次确定 + 第 4 次触发阻断
    assert context.get("game_enter_blocked") is True

    fatal = [s for s in health_fatal_errors(KEYS) if s.name == "game_enter_blocked"]
    assert len(fatal) == 1
    result = fatal[0].when.evaluate(context)
    assert result.satisfied is True
