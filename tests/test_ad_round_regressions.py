"""Multi-frame regressions from QQR-27/28/31 logs, without synthetic icons."""

from types import SimpleNamespace

import pytest

from qqreader.maa import FeatureCatalog, MaaFeatureLocator, RecoResult, Screenshot
from qqreader.page.observation import PageObservation
from qqreader.page.states import Orientation, PageState, RunState
from tests.helpers import make_context, make_recognizer, reward_observation
from tests.test_maa_adapter import FAKE_PNG, FakeMaaClient
from tests.test_qqr31_live_ad import _adapter
from tests.helpers import SimulatedDevice


def observe(context, *texts):
    observation = PageObservation(orientation=Orientation.PORTRAIT, ocr_texts=texts)
    context.update_observation(observation, make_recognizer().evaluate(observation))


def test_each_ad_round_has_its_own_initial_wait():
    adapter = _adapter(SimulatedDevice())
    context = make_context(reward_observation(), run_state=RunState.RUNNING)
    adapter.advance(context)
    observe(context, "广告", "跳过")
    assert adapter.advance(context).actions == ("WAIT",)
    observe(context, "今日已获赠币", "看小视频领好礼", "立即观看")
    adapter.advance(context)
    before = context.now
    observe(context, "广告", "跳过")
    assert adapter.advance(context).actions == ("WAIT",)
    assert context.now - before == 40


@pytest.mark.parametrize("button,key", [
    ("继续观看", "ad_ocr_continue"),
    ("去领取奖励", "ad_ocr_claim_after_exit"),
    ("坚持退出", "ad_ocr_force_exit"),
    ("我要加速", "ad_ocr_accelerate"),
])
def test_live_background_does_not_hide_modal_action(button, key):
    adapter = _adapter(SimulatedDevice())
    context = make_context(reward_observation(), run_state=RunState.RUNNING)
    observe(context, "广告", "直播中", "进入直播间", button)
    context.update_data(ad_scroll_swipes=8)
    assert adapter.advance(context).actions == (f"TAP_FEATURE:{key}",)


@pytest.mark.parametrize("first_box", [(10, 20, 100, 40), None])
def test_locator_rechecks_moved_or_previously_missing_button(first_box):
    boxes = iter([first_box, (500, 700, 100, 40)])
    def recognize(kind, params, shot):
        box = next(boxes)
        return RecoResult.miss(kind) if box is None else RecoResult(kind, True, box=box)
    client = FakeMaaClient(recognizer=recognize)
    observer = SimpleNamespace(last_screenshot=Screenshot(FAKE_PNG, 720, 1280))
    locator = MaaFeatureLocator(client, FeatureCatalog.from_feature_keys(), observer=observer)
    locator.center("reward_ocr_watch")
    observer.last_screenshot = Screenshot(FAKE_PNG, 720, 1280)
    assert locator.center("reward_ocr_watch") == (550, 720)


def test_live_exit_attempt_does_not_restart_eight_swipe_cycle():
    adapter = _adapter(SimulatedDevice())
    context = make_context(reward_observation(), run_state=RunState.RUNNING)
    observe(context, "广告", "直播中", "进入直播间")
    context.update_data(ad_scroll_swipes=8)
    assert adapter.advance(context).actions == ("TAP_POINT",)
    assert adapter.advance(context).actions == ("WAIT",)
    assert adapter.advance(context).actions == ("PRESS_BACK",)


def test_actual_live_ocr_without_ad_label_enters_scroll_branch():
    adapter = _adapter(SimulatedDevice())
    context = make_context(reward_observation(), run_state=RunState.RUNNING)
    observe(context, "直播中", "X", "上滑浏览获取奖励", "ıı进入直播间", "23秒")
    assert context.state is PageState.AD_PLAYING
    assert adapter.advance(context).actions == ("WAIT",)
    assert adapter.advance(context).actions == ("SWIPE",)


def test_captcha_over_live_background_remains_blocking():
    from qqreader.tasks.ad import build_ad_contract
    context = make_context(reward_observation())
    observe(context, "直播中", "进入直播间", "安全验证", "拖动下方滑块完成拼图")
    # TaskRunner checks this guard before page state, success or any action.
    assert build_ad_contract().captcha_condition.evaluate(context).satisfied


def test_game_row_on_reward_page_does_not_stall_ad_navigation():
    adapter = _adapter(SimulatedDevice())
    context = make_context(reward_observation(), run_state=RunState.RUNNING)
    observe(context, "玩游戏领赠币", "去玩游戏", "看小视频领好礼", "立即观看")
    assert context.state is PageState.GAME_ENTRY
    assert adapter.advance(context).actions == ("TAP_FEATURE:reward_ocr_watch",)


def test_obscured_watch_does_not_click_share_or_fixed_point():
    device = SimulatedDevice()
    context = make_context(reward_observation(), run_state=RunState.RUNNING)
    observe(context, "今日已获赠币190", "看小视频领好礼", "立民", "立即分享，朋友在当日完成助力")
    assert _adapter(device).advance(context).actions == ("SWIPE",)
    assert all(call[0] == "swipe" for call in device.calls)


def test_delayed_ad_close_cannot_queue_back_into_bookshelf():
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = make_context(reward_observation(), run_state=RunState.RUNNING)
    observe(context, "直播中", "进入直播间", "已发放")
    context.update_data(ad_scroll_swipes=8)
    adapter.advance(context)
    # Last ad frame remains visible while the close animation is pending.
    assert adapter.advance(context).actions == ("WAIT",)
    observe(context, "今日已获赠币190", "看小视频领好礼", "立即观看")
    adapter.advance(context)
    assert ("press_back",) not in device.calls


def test_live_creative_activity_copy_is_not_game_hall():
    context = make_context(reward_observation())
    observe(context, "直播中", "进入直播间", "周年庆活动", "已发放")
    assert context.state is PageState.AD_PLAYING
