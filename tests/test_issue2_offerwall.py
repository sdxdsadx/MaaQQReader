"""Issue #2: offerwall ads use a bounded fast-abandon path."""

from __future__ import annotations

from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.observation import PageObservation
from qqreader.page.states import Orientation, RunState
from qqreader.tasks.ad import AdTaskAdapter, build_ad_action_plan
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

    assert adapter.advance(context).actions == ("TAP_POINT",)
    assert ("tap_point", 34, 58) in device.calls
    _finish_exit_settle(adapter, context)
    _observe(context, OFFER_TEXT + ("继续观看", "放弃奖励"))

    assert adapter.advance(context).actions == (f"TAP_FEATURE:{ABANDON_KEY}",)
    assert ("tap_feature", ABANDON_KEY) in device.calls


def test_offerwall_without_x_presses_back_then_abandons_reward() -> None:
    device = SimulatedDevice()
    adapter = _adapter(device)
    texts = tuple(text for text in OFFER_TEXT if text != "X")
    context = _context(texts)

    assert adapter.advance(context).actions == ("PRESS_BACK",)
    assert ("press_back",) in device.calls
    _finish_exit_settle(adapter, context)
    _observe(context, texts + ("继续观看", "放弃奖励"))

    assert adapter.advance(context).actions == (f"TAP_FEATURE:{ABANDON_KEY}",)


def test_offerwall_three_ineffective_rounds_restart_app_and_stop_retrying() -> None:
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = _context()

    assert adapter.advance(context).actions == ("TAP_POINT",)
    _finish_exit_settle(adapter, context)
    assert adapter.advance(context).actions == ("TAP_POINT",)
    _finish_exit_settle(adapter, context)
    assert adapter.advance(context).actions == ("TAP_POINT",)
    _finish_exit_settle(adapter, context)
    assert adapter.advance(context).actions == (f"RESTART_APP:{QQ}",)

    assert device.calls.count(("tap_point", 34, 58)) == 3
    assert ("stop_app", QQ) in device.calls
    assert ("launch_app", QQ) in device.calls
