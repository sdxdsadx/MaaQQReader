"""等级页广告 10-13～10-19 实机失败的两类现场（真实 Maa OCR 帧回放）。

A. 赠币广告「暂无可播视频，点击下方广告领取本次激励奖励」弹窗
   （``mfa_20261014_104335_dd9a271c``、``mfa_20261019_160110_39ab3243``）：
   弹窗背后仍能读到「用户等级」，``LevelCoinAdNotStarted`` 把它当成“广告没拉起”空等；
   ``LevelClickCoinAdAgain`` 的「^立即领取$」没有 ROI，点中弹窗里淘宝广告卡的
   「立即领取」(292,849)，跳到「正在跳转 / 下载淘宝」页，``LevelAdUnknownWait`` 空等失败。
   修复：先认弹窗、点弹窗底部 X 关闭，按来源锚点回到原广告的后续核对；
   入口按钮只认等级页右侧按钮列。

B. 积分广告「去浏览15秒 / 我要加速 / 免看此广告」浏览弹层
   （``mfa_20261013_070802_e2cb29f0``、``mfa_20261016_144806_d665eacf``）：
   这一版式没有「Ns后自动放弃」，弹层期间视频暂停；``LevelAdAccelerateWait`` 自己
   循环 120 次（约 5.5 分钟）画面不变后失败。10-08 实机验证过的做法（用户同意）：
   点「我要加速」进落地页停 20 秒，按返回，顶部「奖励已领取｜跳过」后点跳过。
   「去体验9秒 … 9s后自动放弃继续播放视频内」版式会自己回到视频，仍只等待。

帧：``tests/fixtures/level_ad_no_video_20261019.json``（本次摘录）、
``tests/fixtures/level_browse_ad_20261008.json``、
``tests/fixtures/level_points_accelerate_ocr_frames.json``。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.test_qqr54_level_ad_retention import (
    PIPELINE,
    first_match,
    level_pipeline,
    node_hits,
    run_task,
)

pytestmark = pytest.mark.skipif(not PIPELINE.exists(), reason="本机未生成 dev/resource pipeline")

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


NO_VIDEO = _load("level_ad_no_video_20261019.json")
BROWSE = _load("level_browse_ad_20261008.json")
ACCEL = _load("level_points_accelerate_ocr_frames.json")


def frame(source, name):
    return [(text, tuple(box)) for text, box in source[name]["boxes"]]


def center(box):
    x, y, w, h = box
    return x + w // 2, y + h // 2


DIALOG = run_task.LEVEL_NO_VIDEO_DIALOG_NODE
CLOSE = run_task.LEVEL_NO_VIDEO_CLOSE_NODE
ACCELERATE = run_task.LEVEL_BROWSE_ACCELERATE_NODE
BACK = run_task.LEVEL_BROWSE_LANDING_BACK_NODE
WAIT = run_task.LEVEL_ACCELERATE_WAIT_NODE
NO_VIDEO_FRAMES = ("coin_no_video_dialog", "coin_no_video_dialog_1014")
#: 点击赠币入口后链路可能停在的节点（10-19 现场依次经过这几个）。
COIN_OWNERS = ("LevelClickCoinAd", "LevelClickCoinAdAgain", "LevelCoinAdNotStarted")


# ------------------------------------------------------------------ A. 暂无可播视频


@pytest.mark.parametrize("shot", NO_VIDEO_FRAMES)
@pytest.mark.parametrize("current", COIN_OWNERS)
def test_no_video_dialog_is_recognised_before_waiting_or_reclicking(current, shot):
    name, _ = first_match(level_pipeline(), current, frame(NO_VIDEO, shot))
    assert name == DIALOG, f"{current} 在 {shot} 上命中 {name}"


@pytest.mark.parametrize("shot", NO_VIDEO_FRAMES)
def test_no_video_dialog_closes_with_its_bottom_x(shot):
    data = level_pipeline()
    name, box = first_match(data, DIALOG, frame(NO_VIDEO, shot))
    assert name == CLOSE
    cx, cy = center(box)
    assert 330 <= cx <= 390 and 1000 <= cy <= 1060, box
    assert data[CLOSE]["action"] == "Click"


def test_no_video_dialog_never_clicks_the_ad_card():
    """弹窗里淘宝广告卡的「立即领取」(292,849) 不能被当成等级页赠币入口。"""
    data = level_pipeline()
    dialog = frame(NO_VIDEO, "coin_no_video_dialog")
    for name in ("LevelClickCoinAd", "LevelClickCoinAdAgain"):
        assert node_hits(data[name], dialog) is None, name
        box = node_hits(data[name], frame(NO_VIDEO, "level_coin_entry"))
        assert box is not None and center(box)[0] > 560, (name, box)


def test_after_closing_coin_dialog_flow_moves_on_to_points_ad():
    """关闭后按来源锚点回到赠币广告的返回核对，再去找积分广告。"""
    data = level_pipeline()
    anchors = dict(data["LevelClickCoinAd"]["anchor"])
    page = frame(NO_VIDEO, "level_coin_entry")
    name, _ = first_match(data, CLOSE, page, anchors=anchors)
    assert name == "LevelAfterCoinAd"
    assert first_match(data, name, page)[0] == "LevelFindPointsAd"


def test_captcha_stays_ahead_of_no_video_dialog():
    data = level_pipeline()
    for owner in (*COIN_OWNERS, DIALOG, CLOSE):
        nexts = data[owner]["next"]
        assert nexts.index("AdSlideCaptchaDetected") < nexts.index(DIALOG if owner != DIALOG else CLOSE)


# ------------------------------------------------------------------ B. 浏览弹层


BROWSE_FRAMES = (
    (NO_VIDEO, "points_browse_15s_1016"),
    (BROWSE, "browse_offer"),
    (ACCEL, "offer_browse_15s"),
)
#: 积分广告点开后，以及 10-16 现场里自我循环的等待节点。
POINTS_OWNERS = ("LevelClickPointsAd", "LevelClickPointsAdAgain", WAIT, "AdCountdown")


@pytest.mark.parametrize("source,shot", BROWSE_FRAMES)
@pytest.mark.parametrize("current", POINTS_OWNERS)
def test_frozen_browse_offer_clicks_accelerate(current, source, shot):
    name, box = first_match(level_pipeline(), current, frame(source, shot))
    assert name == ACCELERATE, f"{current} 在 {shot} 上命中 {name}"
    cx, cy = center(box)
    assert 300 <= cx <= 420 and 700 <= cy <= 780, box


@pytest.mark.parametrize("shot", ["offer_experience_9s", "offer_auto_abandon_1s"])
@pytest.mark.parametrize("current", POINTS_OWNERS)
def test_auto_abandon_offer_still_only_waits(current, shot):
    """「Ns后自动放弃继续播放视频内」版式会自己回到视频，不进落地页。"""
    name, _ = first_match(level_pipeline(), current, frame(ACCEL, shot))
    assert name == WAIT


def test_landing_page_is_left_with_back_key_only():
    data = level_pipeline()
    assert data[ACCELERATE]["post_delay"] >= 20000
    name, _ = first_match(data, ACCELERATE, frame(BROWSE, "landing_page"))
    assert name == BACK
    assert data[BACK]["action"] == "ClickKey" and data[BACK]["key"] == 4


def test_reward_granted_after_landing_skips_at_top_right():
    data = level_pipeline()
    name, _ = first_match(data, BACK, frame(BROWSE, "reward_granted"))
    assert name == run_task.LEVEL_REWARD_GRANTED_SKIP_NODE
    assert data[name]["target"] == [680, 35]


def test_still_frozen_after_back_accelerates_again_then_gives_up():
    data = level_pipeline()
    shot = frame(NO_VIDEO, "points_browse_15s_1016")
    assert first_match(data, BACK, shot)[0] == ACCELERATE
    used = {ACCELERATE: data[ACCELERATE]["max_hit"]}
    # 加速次数用完：回到原来的跳过 / 放弃 + 换广告路径，不再原地干等 120 次。
    assert first_match(data, BACK, shot, hits=used)[0] == "AdSkipBrowseOffer"


def test_accelerate_ignores_accelerate_reward_popup_button():
    """10-12「我要加速领奖」弹窗仍点「继续播放视频内容」，不点加速（跳第三方应用）。"""
    data = level_pipeline()
    assert node_hits(data[ACCELERATE], [("我要加速领奖", (250, 720, 220, 40))]) is None


def test_overrides_are_idempotent():
    data = level_pipeline()
    run_task._apply_level_ad_runtime_overrides(data)
    for node in data.values():
        nexts = node.get("next") if isinstance(node, dict) else None
        if isinstance(nexts, list):
            names = [n for n in nexts if isinstance(n, str)]
            assert len(names) == len(set(names)), nexts
