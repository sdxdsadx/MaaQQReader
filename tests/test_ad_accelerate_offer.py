"""「获得加速机会」弹窗：点「继续播放视频内容」留在视频里，再补看 30 秒。

2026-10-12 ``DailyAdFlow`` 连续三次 ``ad_exit_unconfirmed``：弹窗上的「我要加速领奖」
含旧文案「我要加速」，被当成加速按钮点掉后跳到第三方应用详情页，倒计时停在 27 秒。
帧数据是失败现场真机截图的原始 Maa OCR（``tests/fixtures/ad_accelerate_offer_ocr_frames.json``）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.observation import PageObservation
from qqreader.page.states import Orientation, PageState, RunState
from qqreader.tasks.common import feature_key
from tests.helpers import SimulatedDevice, make_context, make_recognizer, reward_observation
from tests.test_qqr31_live_ad import _adapter

KEYS = DEFAULT_FEATURE_KEYS
FRAMES = json.loads(
    (Path(__file__).parent / "fixtures" / "ad_accelerate_offer_ocr_frames.json").read_text(encoding="utf-8")
)
OLD_FRAMES = json.loads(
    (Path(__file__).parent / "fixtures" / "ad_failures_20261004.json").read_text(encoding="utf-8")
)
CONTINUE_VIDEO = "TAP_FEATURE:ad_ocr_continue_video"
OFFER_FRAMES = ("offer_popup_27s", "offer_popup_28s", "offer_auto_abandon_10s")


def texts(name: str, frames=FRAMES) -> tuple:
    return tuple(text for text, _ in frames[name]["boxes"])


def observe(context, ocr_texts) -> None:
    observation = PageObservation(orientation=Orientation.PORTRAIT, ocr_texts=tuple(ocr_texts))
    context.update_observation(observation, make_recognizer().evaluate(observation))


def new_round(adapter):
    """从奖励页进入新一轮广告，和实机一样先清掉上一轮的标记。"""
    context = make_context(reward_observation(), run_state=RunState.RUNNING)
    adapter.advance(context)
    return context


def test_feature_key_resolves_to_continue_video_field() -> None:
    assert feature_key(KEYS, KEYS.ad_ocr_continue_video) == "ad_ocr_continue_video"
    assert KEYS.ad_ocr_continue_video == "继续播放视频内容"


@pytest.mark.parametrize("name", OFFER_FRAMES)
def test_offer_popup_taps_continue_video_not_accelerate(name: str) -> None:
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = new_round(adapter)
    observe(context, texts(name))
    assert context.state is PageState.AD_PLAYING
    assert adapter.advance(context).actions == (CONTINUE_VIDEO,)
    assert ("tap_feature", "ad_ocr_accelerate") not in device.calls
    assert ("tap_feature", "ad_ocr_skip") not in device.calls


def test_offer_after_initial_wait_extends_wait_by_30_seconds() -> None:
    """实机顺序：开播 → 等 35 秒（期间弹窗把倒计时停在 27 秒）→ 点继续播放 → 再等 30 秒。"""
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = new_round(adapter)
    observe(context, texts("ad_playing_before_offer"))
    start = context.now
    assert adapter.advance(context).actions == ("WAIT",)
    assert context.now - start == 35
    assert not any(call[0] == "swipe" for call in device.calls)

    observe(context, texts("offer_popup_27s"))
    assert adapter.advance(context).actions == (CONTINUE_VIDEO,)

    observe(context, texts("ad_playing_before_offer"))
    before = context.now
    assert adapter.advance(context).actions == ("WAIT",)
    assert context.now - before == 30


def test_offer_before_initial_wait_waits_base_plus_30_seconds() -> None:
    """18:05:47 的现场：第一帧就是弹窗，点掉后要等原来的 35 秒再加 30 秒。"""
    adapter = _adapter(SimulatedDevice())
    context = new_round(adapter)
    observe(context, texts("offer_auto_abandon_10s"))
    assert adapter.advance(context).actions == (CONTINUE_VIDEO,)
    observe(context, texts("ad_playing_before_offer"))
    before = context.now
    assert adapter.advance(context).actions == ("WAIT",)
    assert context.now - before == 65
    # 加长等待只做一次，之后回到正常的收尾流程。
    before = context.now
    adapter.advance(context)
    assert context.now - before < 30


def test_extended_wait_starts_only_after_popup_is_gone() -> None:
    """点击后重新截图弹窗还在：再点一次，不能当成已经关掉开始计时。"""
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = new_round(adapter)
    for _ in range(2):
        observe(context, texts("offer_popup_28s"))
        assert adapter.advance(context).actions == (CONTINUE_VIDEO,)
    assert device.calls.count(("tap_feature", "ad_ocr_continue_video")) == 2


def test_offer_without_continue_link_waits_and_never_accelerates() -> None:
    """OCR 漏掉底部小字时只等下一帧，不能退回去点「我要加速领奖」。"""
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = new_round(adapter)
    context.update_data(ad_initial_wait_done=True)
    device.calls.clear()  # 进入广告时点「立即观看」的那一下不算
    observe(context, [t for t in texts("offer_popup_27s") if "继续播放视频内容" not in t])
    assert adapter.advance(context).actions == ("WAIT",)
    assert device.calls == []


def test_each_round_gets_its_own_extended_wait() -> None:
    adapter = _adapter(SimulatedDevice())
    context = new_round(adapter)
    observe(context, texts("offer_popup_27s"))
    adapter.advance(context)
    # 弹窗点掉后直接回到了奖励页：上一轮没用掉的加长等待不能带到下一轮。
    observe(context, ("今日已获赠币", "看小视频领好礼", "立即观看"))
    adapter.advance(context)
    observe(context, texts("ad_playing_before_offer"))
    before = context.now
    assert adapter.advance(context).actions == ("WAIT",)
    assert context.now - before == 35


def test_reward_granted_popup_is_not_treated_as_accelerate_offer() -> None:
    """10-04 的「恭喜提前获得奖励」弹窗也有「继续播放视频内容」，但奖励已到手，仍走原出口。"""
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = new_round(adapter)
    context.update_data(ad_initial_wait_done=True)
    observe(context, texts("ad_reward_popup", OLD_FRAMES))
    step = adapter.advance(context)
    assert step.actions != (CONTINUE_VIDEO,)
    assert ("tap_feature", "ad_ocr_continue_video") not in device.calls


def test_exit_confirm_over_offer_keeps_existing_exit_handling() -> None:
    """10-04 的帧：「确定要退出吗」叠在同款弹窗上，仍由原来的退出分支点「坚持退出」。"""
    latest = json.loads(
        (Path(__file__).parent / "fixtures" / "ad_level_latest_20261004.json").read_text(encoding="utf-8")
    )
    device = SimulatedDevice()
    adapter = _adapter(device)
    context = new_round(adapter)
    device.calls.clear()
    observe(context, texts("browse_retention", latest))
    adapter.advance(context)
    assert device.calls == [("tap_feature", "ad_ocr_force_exit")]


def test_plain_accelerate_button_still_tapped() -> None:
    """QQR-30 的旧版「我要加速」（没有继续播放选项）行为不变。"""
    adapter = _adapter(SimulatedDevice())
    context = new_round(adapter)
    context.update_data(ad_initial_wait_done=True)
    observe(context, ("广告", "我要加速"))
    assert adapter.advance(context).actions == ("TAP_FEATURE:ad_ocr_accelerate",)

# ------------------------------------------------------------------ 等级广告（旧 pipeline）

from tests.test_qqr54_level_ad_retention import first_match, level_pipeline  # noqa: E402

import run_task  # noqa: E402  （上一行的导入已把 scripts/ 加进 sys.path）

DECLINE = run_task.LEVEL_ACCELERATE_DECLINE_NODE
LEVEL_OWNERS = ("LevelClickPointsAd", "LevelClickPointsAdAgain", "AdCountdown", "AdScrollDownRepeat")


def boxes(name: str, frames=FRAMES):
    return [(text, tuple(box)) for text, box in frames[name]["boxes"]]


@pytest.mark.parametrize("name", OFFER_FRAMES)
@pytest.mark.parametrize("owner", LEVEL_OWNERS)
def test_level_pipeline_clicks_continue_video_on_offer(name: str, owner: str) -> None:
    data = level_pipeline()
    hit, box = first_match(data, owner, boxes(name))
    assert hit == DECLINE, (owner, name, hit)
    assert "继续播放视频内容" in dict((tuple(b), t) for t, b in boxes(name))[box]


def test_level_pipeline_reaches_continue_video_through_countdown() -> None:
    """个别 next 列表里 AdCountdown 排在前面：等一拍后仍会落到「继续播放视频内容」。"""
    data = level_pipeline()
    for owner in (n for n, v in data.items() if isinstance(v, dict) and DECLINE in (v.get("next") or [])):
        hit, _ = first_match(data, owner, boxes("offer_popup_27s"))
        if hit != DECLINE:
            assert hit == "AdCountdown", (owner, hit)
            hit, _ = first_match(data, hit, boxes("offer_popup_27s"))
        assert hit == DECLINE, owner


def test_level_decline_waits_30_seconds_and_is_bounded() -> None:
    node = level_pipeline()[DECLINE]
    assert node["action"] == "Click"
    assert node["post_delay"] == 30000
    assert node["max_hit"] == 3
    assert node["next"][:2] == list(run_task.LEVEL_CAPTCHA_NODES)


@pytest.mark.parametrize("name", ["ad_playing_before_offer", "after_wrong_accelerate_tap"])
def test_level_pipeline_waits_on_reward_countdown_instead_of_skipping(name: str) -> None:
    """「还需观看N秒领奖｜跳过」原先被 AdSkipBrowseOffer 点掉顶部「跳过」。"""
    data = level_pipeline()
    for owner in ("LevelClickPointsAd", "AdScrollDownRepeat"):
        hit, _ = first_match(data, owner, boxes(name))
        assert hit == run_task.LEVEL_ACCELERATE_WAIT_NODE, (owner, hit)


def test_level_reward_granted_popup_still_exits_by_top_skip() -> None:
    data = level_pipeline()
    for owner in ("LevelClickPointsAd", "AdCountdown", "AdScrollDownRepeat"):
        hit, box = first_match(data, owner, boxes("ad_reward_popup", OLD_FRAMES))
        assert hit == run_task.LEVEL_REWARD_GRANTED_SKIP_NODE, (owner, hit)
        assert box == (536, 14, 172, 27)  # 真实 OCR「奖励已领取跳过」
    assert data[hit]["next"] == data["AdSkipBrowseOffer"]["next"]


def test_level_offer_overrides_are_idempotent() -> None:
    import copy

    once = level_pipeline()
    twice = copy.deepcopy(once)
    run_task._apply_level_ad_runtime_overrides(twice)
    assert once == twice
