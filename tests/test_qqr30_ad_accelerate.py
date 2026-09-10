"""QQR-30：广告播放页对齐旧版「我要加速」等动作。"""

from __future__ import annotations

from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.states import RunState
from qqreader.tasks.ad import AdTaskAdapter, build_ad_action_plan
from qqreader.tasks.common import feature_key
from tests.helpers import QQ, SimulatedDevice, ad_playing_observation, make_context

KEYS = DEFAULT_FEATURE_KEYS
ACCELERATE_KEY = feature_key(KEYS, KEYS.ad_ocr_accelerate)


def _adapter(device: SimulatedDevice) -> AdTaskAdapter:
    return AdTaskAdapter(
        device=device,
        plan=build_ad_action_plan(KEYS),
        expected_package=QQ,
        popup_feature=feature_key(KEYS, KEYS.popup_close),
    )


def _playing_context(**overrides):
    context = make_context(
        ad_playing_observation(**overrides),
        run_state=RunState.RUNNING,
    )
    context.update_data(ad_initial_wait_done=True)
    return context


def test_ad_playing_taps_accelerate() -> None:
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = _playing_context(ocr_texts=("广告", "我要加速"))
    step = adapter.advance(context)
    assert step.actions == (f"TAP_FEATURE:{ACCELERATE_KEY}",)
    assert ("tap_feature", ACCELERATE_KEY) in device.calls


def test_ad_playing_closes_completed_popup() -> None:
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = _playing_context(ocr_texts=("广告", "恭喜获得奖励"))
    step = adapter.advance(context)
    assert step.actions == ("TAP_POINT",)
    assert ("tap_point", 48, 70) in device.calls
