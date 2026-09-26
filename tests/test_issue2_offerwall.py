"""Issue #2: offerwall ads wait before a single verified exit."""

from __future__ import annotations

from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.observation import PageObservation
from qqreader.page.states import Orientation, RunState
from qqreader.tasks.ad import AdTaskAdapter, build_ad_action_plan, build_ad_contract
from qqreader.tasks.common import feature_key
from tests.helpers import QQ, SimulatedDevice, ad_playing_observation, make_context, make_recognizer


KEYS = DEFAULT_FEATURE_KEYS
ABANDON_KEY = feature_key(KEYS, KEYS.ad_ocr_abandon_reward)
OFFER_TEXT = (
    "X",
    "观看30秒，可获得奖励",
    "跳转详情页或第三方应用",
    "了解详情",
    "广告",
)


def _adapter(device: SimulatedDevice) -> AdTaskAdapter:
    return AdTaskAdapter(
        device=device,
        plan=build_ad_action_plan(KEYS),
        expected_package=QQ,
        popup_feature=feature_key(KEYS, KEYS.popup_close),
    )


def _context(texts=OFFER_TEXT):
    context = make_context(
        ad_playing_observation(ocr_texts=texts),
        run_state=RunState.RUNNING,
    )
    return context


def _observe(context, texts) -> None:
    observation = PageObservation(
        current_app=QQ,
        orientation=Orientation.PORTRAIT,
        ocr_texts=tuple(texts),
        structure={"ad.video_surface": 0.8},
    )
    context.update_observation(observation, make_recognizer().evaluate(observation))


def _finish_exit_settle(adapter, context) -> None:
    assert adapter.advance(context).actions == ("WAIT",)


def test_offerwall_with_x_clicks_x_then_abandon_reward() -> None:
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = _context()

    _wait_for_video(adapter, context, device)
    assert adapter.advance(context).actions == ("TAP_POINT",)
    assert ("tap_point", 48, 70) in device.calls
    _finish_exit_settle(adapter, context)
    _observe(context, OFFER_TEXT + ("继续观看", "放弃奖励"))

    assert adapter.advance(context).actions == (f"TAP_FEATURE:{ABANDON_KEY}",)
    assert ("tap_feature", ABANDON_KEY) in device.calls


def test_offerwall_copy_is_recognized_as_ad_playing_without_app_identity() -> None:
    observation = PageObservation(
        current_app=None,
        orientation=Orientation.PORTRAIT,
        ocr_texts=("X", "跳转详情页或第三方应用", "了解详情", "大众点评"),
    )

    decision = make_recognizer().evaluate(observation)

    assert decision.state.value == "AD_PLAYING"
    assert decision.is_confirmed


def test_offerwall_without_x_presses_back_then_abandons_reward() -> None:
    device = SimulatedDevice()
    adapter = _adapter(device)
    texts = tuple(text for text in OFFER_TEXT if text != "X")
    context = _context(texts)

    _wait_for_video(adapter, context, device)
    assert adapter.advance(context).actions == ("PRESS_BACK",)
    assert ("press_back",) in device.calls
    _finish_exit_settle(adapter, context)
    _observe(context, texts + ("继续观看", "放弃奖励"))

    assert adapter.advance(context).actions == (f"TAP_FEATURE:{ABANDON_KEY}",)


def test_offerwall_after_countdown_still_uses_fast_exit() -> None:
    device = SimulatedDevice()
    context = _context((
        "X",
        "跳转详情页或第三方应用",
        "了解详情",
        "大众点评",
    ))

    adapter = _adapter(device)
    _wait_for_video(adapter, context, device)
    assert adapter.advance(context).actions == ("TAP_POINT",)
    assert ("tap_point", 48, 70) in device.calls


def _wait_for_video(adapter, context, device):
    started = context.now
    assert adapter.advance(context).actions == ("WAIT",)
    assert context.now - started == 35.0
    assert device.calls == []


def test_offerwall_corrupted_countdown_waits_before_back():
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = _context(("大众点29秒，", "可获得奖励", "了解详情", "跳转详情页或第三方应用"))
    _wait_for_video(adapter, context, device)
    assert adapter.advance(context).actions == ("PRESS_BACK",)
    _finish_exit_settle(adapter, context)
    for _ in range(80):
        adapter.advance(context)
    # 返回键 20 秒无效后，依次改点左上角 X、再按一次返回；仍无效才判失败。
    assert device.calls == [("press_back",), ("tap_point", 48, 70), ("press_back",)]
    assert context.get("ad_exit_error")


def test_offerwall_reward_granted_card_taps_x_instead_of_back():
    """2026-09-23：「恭喜获得奖励」+「了解详情」卡不响应返回键，必须点 X。"""
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = _context(("恭喜获得奖励", "了解详情", "跳转详情页或第三方应用"))
    _wait_for_video(adapter, context, device)
    assert adapter.advance(context).actions == ("TAP_POINT",)
    assert device.calls == [("tap_point", 48, 70)]


def test_rating_end_card_closes_once_after_video_exit():
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = _context(tuple(t for t in OFFER_TEXT if t != "X"))
    _wait_for_video(adapter, context, device)
    assert adapter.advance(context).actions == ("PRESS_BACK",)
    _finish_exit_settle(adapter, context)
    _observe(context, ("大众点评", "5.0", "了解详情", "跳转详情页或第三方应用"))
    assert adapter.advance(context).actions == ("TAP_POINT",)
    _finish_exit_settle(adapter, context)
    adapter.advance(context)
    assert device.calls == [("press_back",), ("tap_point", 53, 112)]


def test_entered_ad_satisfies_ready_without_reward_banner():
    context = _context(("大众点29秒，", "可获得奖励", "了解详情", "跳转详情页或第三方应用"))
    assert build_ad_contract().ready_condition.evaluate(context).satisfied
    assert not build_ad_contract().success_condition.evaluate(context).satisfied
