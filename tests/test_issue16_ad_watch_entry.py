"""issue #16：广告主链复用奖励页滚动入口导航。"""

from __future__ import annotations

import pytest

from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.states import RunState
from qqreader.tasks.ad import AdTaskAdapter, build_ad_action_plan
from qqreader.tasks.common import feature_key
from tests.helpers import QQ, SimulatedDevice, make_context, reward_observation
from tests.test_issue15_reward_nav import FakeClient, Frame

KEYS = DEFAULT_FEATURE_KEYS


@pytest.fixture
def adapter_factory():
    def build(client: FakeClient, *, max_scrolls: int = 8) -> AdTaskAdapter:
        return AdTaskAdapter(
            device=SimulatedDevice(),
            plan=build_ad_action_plan(KEYS),
            expected_package=QQ,
            popup_feature=feature_key(KEYS, KEYS.popup_close),
            navigation_client=client,
            max_scrolls=max_scrolls,
            entry_settle_seconds=0,
        )

    return build


def _advance(adapter: AdTaskAdapter):
    context = make_context(reward_observation(), run_state=RunState.RUNNING)
    return context, adapter.advance(context)


def test_watch_entry_on_first_screen_is_clicked(adapter_factory) -> None:
    client = FakeClient([[('立即观看', (540, 1080, 120, 50))]])

    context, step = _advance(adapter_factory(client))

    assert step.progress is True
    assert step.description == '滚动定位并点击广告入口“立即观看”'
    assert client.clicks == [(600, 1105)]
    assert client.swipes == []
    assert context.get("ad_watch_entry_error") is None


def test_watch_entry_below_fold_is_clicked_after_n_scrolls(adapter_factory) -> None:
    frames: list[Frame] = [
        [("今日游戏", (50, 800, 180, 40))],
        [("玩游戏领赠币", (50, 500, 200, 40))],
        [("立即观看", (520, 980, 140, 50))],
    ]
    client = FakeClient(frames)

    _, step = _advance(adapter_factory(client, max_scrolls=4))

    assert step.progress is True
    assert client.clicks == [(590, 1005)]
    assert client.swipes == [
        (360, 1150, 360, 400, 500),
        (360, 1150, 360, 400, 500),
    ]


def test_missing_watch_entry_reports_readable_error(adapter_factory) -> None:
    client = FakeClient([[('今日游戏', (50, 800, 180, 40))]])

    context, step = _advance(adapter_factory(client, max_scrolls=3))

    assert step.progress is False
    assert step.actions == ("REOBSERVE",)
    assert step.description == (
        '奖励页广告入口查找失败：首屏及最多 3 次下滑均未找到“立即观看”'
    )
    assert context.get("ad_watch_entry_error") == step.description
    assert client.clicks == []
    assert len(client.swipes) == 3
