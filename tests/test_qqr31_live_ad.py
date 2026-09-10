"""QQR-31：直播间/浏览类广告每 5 秒下滑直至等待结束。"""

from __future__ import annotations

from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.states import RunState
from qqreader.tasks.ad import AdTaskAdapter, build_ad_action_plan
from qqreader.tasks.common import feature_key
from tests.helpers import QQ, SimulatedDevice, ad_playing_observation, make_context

KEYS = DEFAULT_FEATURE_KEYS


def _adapter(device: SimulatedDevice) -> AdTaskAdapter:
    return AdTaskAdapter(
        device=device,
        plan=build_ad_action_plan(KEYS),
        expected_package=QQ,
        popup_feature=feature_key(KEYS, KEYS.popup_close),
    )


def _context(*, ocr_texts, **data):
    context = make_context(
        ad_playing_observation(ocr_texts=ocr_texts),
        run_state=RunState.RUNNING,
    )
    context.update_data(**data)
    return context


def test_live_ad_waits_then_swipes() -> None:
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = _context(ocr_texts=("广告", "进入直播间", "16秒"))
    first = adapter.advance(context)
    assert first.actions == ("WAIT",)
    second = adapter.advance(context)
    assert second.actions == ("SWIPE",)
    assert ("swipe", 360, 1000, 360, 350, 500) in device.calls


def test_live_ad_exits_when_countdown_low() -> None:
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = _context(ocr_texts=("广告", "进入直播间", "2秒"))
    step = adapter.advance(context)
    assert step.actions == ("TAP_POINT",)
    assert ("tap_point", 55, 118) in device.calls


def test_live_ad_exits_after_max_swipes() -> None:
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = _context(
        ocr_texts=("广告", "直播中", "16秒"),
        ad_scroll_phase="wait",
        ad_scroll_swipes=8,
    )
    step = adapter.advance(context)
    assert step.actions == ("TAP_POINT",)
    assert ("tap_point", 55, 118) in device.calls
