"""QQR-27：广告流程入口与播放页修复回归测试。"""

from __future__ import annotations

import re

from qqreader.maa.catalog import FeatureCatalog
from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.states import PageState, RunState
from qqreader.runtime.clock import FakeClock
from qqreader.tasks.ad import AdTaskAdapter, build_ad_action_plan
from qqreader.tasks.common import feature_key
from tests.helpers import (
    QQ,
    SimulatedDevice,
    ad_playing_observation,
    make_context,
    reward_observation,
)

KEYS = DEFAULT_FEATURE_KEYS
WATCH_KEY = feature_key(KEYS, KEYS.reward_ocr_watch)
WATCH_PARTIAL_KEY = feature_key(KEYS, KEYS.reward_ocr_watch_partial)


def test_home_reward_entry_matches_both_shelf_texts() -> None:
    catalog = FeatureCatalog.from_feature_keys(KEYS)
    asset = catalog.get("home_ocr_reward_entry")
    assert asset is not None
    pattern = re.compile(asset.text)
    assert pattern.search("本周阅读时长/领赠币>")
    assert pattern.search("再读7分钟领20赠币>")


def test_ad_plan_home_uses_home_reward_ocr() -> None:
    plan = build_ad_action_plan(KEYS)
    assert plan.action_for(PageState.HOME).target == "home_ocr_reward_entry"


def _adapter(device: SimulatedDevice) -> AdTaskAdapter:
    return AdTaskAdapter(
        device=device,
        plan=build_ad_action_plan(KEYS),
        expected_package=QQ,
        popup_feature=feature_key(KEYS, KEYS.popup_close),
    )


def test_reward_watch_uses_ocr_feature() -> None:
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = make_context(reward_observation(), run_state=RunState.RUNNING)
    step = adapter.advance(context)
    assert step.actions == (f"TAP_FEATURE:{WATCH_KEY}",)
    assert ("tap_feature", WATCH_KEY) in device.calls


def test_partial_watch_moves_obscured_card_before_reobserving() -> None:
    device = SimulatedDevice(tap_results={WATCH_PARTIAL_KEY: False})
    adapter = _adapter(device)
    context = make_context(
        reward_observation(ocr=("看小视频领好礼", "立")),
        run_state=RunState.RUNNING,
    )
    step = adapter.advance(context)
    assert ("tap_feature", WATCH_PARTIAL_KEY) not in device.calls
    assert step.actions == ("SWIPE",)
    assert ("tap_point", 600, 1078) not in device.calls


def test_ad_play_waits_40_seconds_before_handling_buttons() -> None:
    clock = FakeClock()
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = make_context(
        ad_playing_observation(),
        clock=clock,
        run_state=RunState.RUNNING,
    )
    step = adapter.advance(context)
    assert step.actions == ("WAIT",)
    assert clock.now() == 40.0
