"""等级页积分广告的浏览加速等待（2026-10-10 17:24 实机失败现场）。

用本机真实 pipeline（``dev/resource/pipeline/qq_reader_trial.json``）叠加
``_apply_level_ad_runtime_overrides``，再用 ``tests/fixtures/level_points_accelerate_ocr_frames.json``
里的真实 OCR 框，按 MaaFramework 的 next 列表顺序判断「第一个命中的节点」。
OCR 节点逐框正则匹配（有 roi 时只看框中心在 roi 内的框）；没有 recognition 的节点视为直接命中。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_task  # noqa: E402

PIPELINE = ROOT / "dev" / "resource" / "pipeline" / "qq_reader_trial.json"
FRAMES = json.loads(
    (Path(__file__).parent / "fixtures" / "level_points_accelerate_ocr_frames.json").read_text(encoding="utf-8")
)
WAIT = run_task.LEVEL_ACCELERATE_WAIT_NODE

Box = Tuple[int, int, int, int]

#: 「去浏览15秒 / 我要加速」(offer_browse_15s) 不在此列：该版式没有「Ns后自动放弃」，
#: 10-13、10-16 实机原地等 120 次画面不变；现在点「我要加速」，见
#: ``tests/test_level_ad_no_video_browse.py::test_frozen_browse_offer_clicks_accelerate``。
OFFER_FRAMES = (
    "offer_experience_9s",
    "offer_auto_abandon_1s",
    "video_skip_27s",
    "video_skip_24s",
)
#: 点击「看小视频」后、或广告内各节点的 next 列表所在节点。
OWNERS = ("LevelClickPointsAd", "LevelClickPointsAdAgain", "AdCountdown", "AdScrollDownRepeat")


def _pipeline() -> Dict[str, Any]:
    data = json.loads(PIPELINE.read_text(encoding="utf-8"))
    run_task._apply_level_ad_runtime_overrides(data)
    return data


def _boxes(name: str) -> List[Tuple[str, Box]]:
    return [(text, tuple(box)) for text, box in FRAMES[name]["boxes"]]


def _in_roi(box: Box, roi: Optional[List[int]]) -> bool:
    if not roi:
        return True
    x, y, w, h = box
    cx, cy = x + w / 2, y + h / 2
    rx, ry, rw, rh = roi
    return rx <= cx <= rx + rw and ry <= cy <= ry + rh


def _node_matches(node: Dict[str, Any], boxes: List[Tuple[str, Box]]) -> bool:
    if "recognition" not in node:
        return True
    if node["recognition"] != "OCR":
        return False
    expected = node.get("expected")
    patterns = expected if isinstance(expected, list) else [expected]
    return any(
        re.search(pattern, text)
        for text, box in boxes
        if _in_roi(box, node.get("roi"))
        for pattern in patterns
    )


def first_hit(data: Dict[str, Any], owner: str, boxes: List[Tuple[str, Box]]) -> Optional[str]:
    for name in data[owner]["next"]:
        node = data.get(name)
        if node is None:
            continue
        if _node_matches(node, boxes):
            return name
    return None


@pytest.mark.parametrize("frame", OFFER_FRAMES)
@pytest.mark.parametrize("owner", OWNERS)
def test_browse_offer_and_skip_countdown_wait_instead_of_clicking_skip(frame, owner):
    data = _pipeline()
    hit = first_hit(data, owner, _boxes(frame))
    assert hit == WAIT, f"{owner} 在 {frame} 上命中 {hit}"
    assert hit != "AdSkipBrowseOffer"


@pytest.mark.parametrize("owner", OWNERS)
def test_retention_popup_continue_comes_before_wait(owner):
    data = _pipeline()
    assert first_hit(data, owner, _boxes("retention_popup_28s")) == "LevelAdRetentionContinue"


def test_normal_countdown_keeps_countdown_branch():
    data = _pipeline()
    frame = _boxes("countdown_27s_reward_hint")
    assert first_hit(data, "LevelClickPointsAd", frame) == "AdCountdown"
    assert first_hit(data, "AdCountdown", frame) == "AdCountdown"


def test_wait_sits_after_guards_and_before_skip_in_points_ad_list():
    nexts = _pipeline()["LevelClickPointsAd"]["next"]
    assert nexts.index("AdSlideCaptchaDetected") < nexts.index("LevelAdRetentionContinue") < nexts.index(WAIT)
    assert nexts.index(WAIT) < nexts.index("AdSkipBrowseOffer")


@pytest.mark.parametrize(
    "text",
    ["去体验9秒可立即领奖|跳过", "去浏览15秒", "9s后自动放弃继续播放视频内", "可提前19秒领奖", "27s|跳过", "28s跳过"],
)
def test_wait_pattern_matches_browse_and_skip_countdown_texts(text):
    assert _node_matches(_pipeline()[WAIT], [(text, (360, 20, 100, 30))])


@pytest.mark.parametrize(
    "text",
    ["观看27秒，可获得奖励", "注意：请点击确认领取！", "继续观看", "再看28s可领取奖励", "恭喜获得奖励", "我的"],
)
def test_wait_pattern_ignores_countdown_reward_and_popup_texts(text):
    assert not _node_matches(_pipeline()[WAIT], [(text, (360, 600, 100, 30))])


def test_raw_pipeline_is_untouched_so_daily_ad_flow_is_unaffected():
    raw = json.loads(PIPELINE.read_text(encoding="utf-8"))
    assert WAIT not in raw
    for node in raw.values():
        if isinstance(node, dict) and isinstance(node.get("next"), list):
            assert WAIT not in node["next"]


def test_wait_node_is_bounded_and_passive():
    node = _pipeline()[WAIT]
    assert node["action"] == "DoNothing"
    assert node["post_delay"] > 0
    assert 1 <= node["max_hit"] <= 240
