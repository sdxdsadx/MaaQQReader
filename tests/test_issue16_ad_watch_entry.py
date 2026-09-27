"""issue #16：广告主链复用奖励页滚动入口导航。"""

from __future__ import annotations

import pytest

from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.states import RunState
from qqreader.tasks.ad import AdTaskAdapter, build_ad_action_plan, build_ad_contract
from qqreader.tasks.common import feature_key
from tests.helpers import QQ, SimulatedDevice, home_observation, make_context, reward_observation
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


def test_watch_entry_click_waits_for_async_ad_transition(adapter_factory) -> None:
    client = FakeClient([[('立即观看', (540, 1080, 120, 50))]])
    adapter = adapter_factory(client)

    context, first = _advance(adapter)
    second = adapter.advance(context)

    assert first.progress is True
    assert second.actions == ("WAIT",)
    assert context.clock.sleeps == [8.0]
    assert client.clicks == [(600, 1105)]
    assert client.swipes == []


def test_ignored_watch_entry_click_reopens_reward_page_after_three_rounds(
    adapter_factory,
) -> None:
    client = FakeClient([[('立即观看', (540, 1080, 120, 50))]])
    adapter = adapter_factory(client)
    context, _ = _advance(adapter)

    actions = []
    for _ in range(3):
        actions.append(adapter.advance(context).actions)  # transition wait
        actions.append(adapter.advance(context).actions)  # retry or BACK

    assert actions[-1] == ("PRESS_BACK",)
    assert len(client.clicks) == 3


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


def test_home_reuses_reward_page_navigation_for_changed_entry_copy(adapter_factory) -> None:
    client = FakeClient(
        [
            [("书架", (20, 30, 60, 30)), ("554分钟", (70, 150, 100, 40)),
             ("时长兑赠币，立即领取", (60, 180, 280, 40))],
            [("看小视频领好礼", (60, 1100, 260, 50))],
        ]
    )
    adapter = adapter_factory(client)
    context = make_context(home_observation(), run_state=RunState.RUNNING)

    step = adapter.advance(context)

    assert step.progress is True
    assert step.description == "从首页定位奖励入口并确认进入奖励页"
    assert client.clicks == [(200, 200)]
    assert context.get("ad_watch_entry_error") is None


def test_home_entry_error_does_not_stay_fatal_after_reward_page_arrives() -> None:
    contract = build_ad_contract(KEYS)
    context = make_context(home_observation(), run_state=RunState.RUNNING)
    context.update_data(
        ad_watch_entry_error="无法从首页定位奖励入口并确认进入奖励页",
        ad_watch_entry_error_state="HOME",
    )

    assert next(rule for rule in contract.fatal_error if rule.name == "ad_watch_entry_not_found").when.evaluate(context).satisfied is True

    reward_context = make_context(reward_observation(), run_state=RunState.RUNNING)
    reward_context.update_data(
        ad_watch_entry_error="无法从首页定位奖励入口并确认进入奖励页",
        ad_watch_entry_error_state="HOME",
    )
    assert next(rule for rule in contract.fatal_error if rule.name == "ad_watch_entry_not_found").when.evaluate(reward_context).satisfied is False
