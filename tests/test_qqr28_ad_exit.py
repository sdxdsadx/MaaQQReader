"""QQR-28：退出广告后误点书本的回归测试。"""

from __future__ import annotations

from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.states import RunState
from qqreader.tasks.ad import AdTaskAdapter, build_ad_action_plan
from qqreader.tasks.common import feature_key
from tests.helpers import QQ, SimulatedDevice, make_context, reward_observation

KEYS = DEFAULT_FEATURE_KEYS
WATCH_KEY = feature_key(KEYS, KEYS.reward_ocr_watch)


def _adapter(device: SimulatedDevice) -> AdTaskAdapter:
    return AdTaskAdapter(
        device=device,
        plan=build_ad_action_plan(KEYS),
        expected_package=QQ,
        popup_feature=feature_key(KEYS, KEYS.popup_close),
    )


def test_reward_home_without_banner_scrolls_instead_of_clicking() -> None:
    device = SimulatedDevice()
    adapter = _adapter(device)
    # 只有残留的「立即观看」，没有广告卡标题：不能点击，只能滚动。
    context = make_context(
        reward_observation(ocr=("立即观看",)),
        run_state=RunState.RUNNING,
    )
    step = adapter.advance(context)
    assert step.actions == ("SWIPE",)
    assert ("tap_feature", WATCH_KEY) not in device.calls


def test_reward_home_with_banner_and_watch_clicks() -> None:
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = make_context(reward_observation(), run_state=RunState.RUNNING)
    step = adapter.advance(context)
    assert step.actions == (f"TAP_FEATURE:{WATCH_KEY}",)
    assert ("tap_feature", WATCH_KEY) in device.calls
