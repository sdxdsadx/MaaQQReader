"""QQR-54：等级页广告倒计时识别与「继续观看 / 放弃奖励」挽留弹窗。

用本机真实 pipeline（``dev/resource/pipeline/qq_reader_trial.json``，与
``test_issue13_legacy_timeout`` 相同的依赖）叠加 ``_apply_level_ad_runtime_overrides``，
再用 2026-09-27 失败现场的真实 OCR 帧（``tests/fixtures/level_ad_ocr_frames.json``）
按 MaaFramework 的 next 列表顺序模拟识别：OCR 节点逐框正则匹配（有 roi 时只看
roi 内的框），无 recognition 的节点直接命中，达到 max_hit 的节点跳过。
TemplateMatch 等无法离线评估的节点视为未命中。
"""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_task  # noqa: E402

PIPELINE = ROOT / "dev" / "resource" / "pipeline" / "qq_reader_trial.json"
FRAMES = json.loads(
    (Path(__file__).parent / "fixtures" / "level_ad_ocr_frames.json").read_text(encoding="utf-8")
)

Box = Tuple[int, int, int, int]


def frame(name: str) -> List[Tuple[str, Box]]:
    return [(text, tuple(box)) for text, box in FRAMES[name]["boxes"]]


def raw_pipeline() -> Dict[str, Any]:
    return json.loads(PIPELINE.read_text(encoding="utf-8"))


def level_pipeline() -> Dict[str, Any]:
    data = raw_pipeline()
    run_task._apply_level_ad_runtime_overrides(data)
    return data


def _in_roi(box: Box, roi: Optional[List[int]]) -> bool:
    if not roi:
        return True
    x, y, w, h = box
    cx, cy = x + w / 2, y + h / 2
    rx, ry, rw, rh = roi
    return rx <= cx <= rx + rw and ry <= cy <= ry + rh


def node_hits(node: Dict[str, Any], boxes: List[Tuple[str, Box]]) -> Optional[Box]:
    reco = node.get("recognition", "DirectHit")
    if reco == "DirectHit":
        return (0, 0, 0, 0)
    if reco != "OCR":
        return None
    expected = node.get("expected")
    patterns = expected if isinstance(expected, list) else [expected]
    for text, box in boxes:
        if not _in_roi(box, node.get("roi")):
            continue
        if any(re.search(pattern, text) for pattern in patterns):
            return box
    return None


def first_match(
    data: Dict[str, Any],
    current: str,
    boxes: List[Tuple[str, Box]],
    hits: Optional[Dict[str, int]] = None,
) -> Tuple[str, Box]:
    hits = hits if hits is not None else {}
    for name in data[current]["next"]:
        node = data[name]
        if hits.get(name, 0) >= node.get("max_hit", 10**9):
            continue
        box = node_hits(node, boxes)
        if box is not None:
            return name, box
    raise AssertionError(f"{current} 的 next 无一命中")


# ------------------------------------------------------------------ 复现


def test_original_chain_only_presses_back_on_retention_popup() -> None:
    """复现：原链在挽留弹窗上只会落到返回键节点（返回对弹窗无效）。"""
    data = raw_pipeline()
    for current in ("AdCloseByBackKey", "AdBackUntilRewardOrShelf"):
        name, _ = first_match(data, current, frame("retention_popup"))
        assert data[name].get("action") == "ClickKey", name


def test_original_countdown_misses_truncated_timer() -> None:
    """复现：「观看20秒」不满足原 AdCountdown，链路会去关广告或下滑。"""
    data = raw_pipeline()
    assert node_hits(data["AdCountdown"], frame("countdown_20s")) is None
    name, _ = first_match(data, "AdScrollDownRepeat", frame("countdown_17s"))
    assert name == "AdBrowseOfferModal"


# ------------------------------------------------------------------ 修复后


def test_truncated_countdown_waits_instead_of_closing() -> None:
    data = level_pipeline()
    for frame_name in ("countdown_20s", "countdown_17s"):
        for current in ("AdScrollDownRepeat", "LevelClickCoinAd", "LevelClickPointsAd", "AdSkipBrowseOffer"):
            name, _ = first_match(data, current, frame(frame_name))
            assert name == "AdCountdown", (current, frame_name, name)


def test_retention_popup_clicks_continue_watching_from_every_entry() -> None:
    data = level_pipeline()
    popup = frame("retention_popup")
    for current in run_task.LEVEL_RETENTION_ENTRY_NODES:
        name, box = first_match(data, current, popup)
        assert name == "LevelAdRetentionContinue", (current, name)
        assert box == (291, 754, 133, 39)  # 真实 OCR「继续观看」框


def test_popup_body_text_is_not_mistaken_for_countdown() -> None:
    data = level_pipeline()
    body = [item for item in frame("retention_popup") if "30秒" in item[0]]
    assert body and node_hits(data["AdCountdown"], body) is None


def test_repeated_popup_gives_up_after_three_continues() -> None:
    data = level_pipeline()
    hits = {"LevelAdRetentionContinue": 3}
    name, box = first_match(data, "AdCloseByBackKey", frame("retention_popup"), hits)
    assert name == "LevelAdRetentionGiveUp"
    assert box == (299, 840, 119, 37)  # 真实 OCR「放弃奖励」框
    assert data["LevelAdRetentionGiveUp"]["next"][-2:] == ["AdReturnedAfterClose", "AdCloseByBackKey"]


def test_captcha_nodes_stay_ahead_of_retention_handling() -> None:
    data = level_pipeline()
    nexts = data["AdScrollDownRepeat"]["next"]
    assert nexts.index("AdCaptchaDetected") < nexts.index("LevelAdRetentionContinue")
    for name in run_task.LEVEL_RETENTION_NODES:
        assert data[name]["next"][:2] == list(run_task.LEVEL_CAPTCHA_NODES)


def test_retention_overrides_are_idempotent_and_resolve() -> None:
    once = level_pipeline()
    twice = copy.deepcopy(once)
    run_task._apply_level_ad_runtime_overrides(twice)
    for name in run_task.LEVEL_RETENTION_ENTRY_NODES:
        assert once[name]["next"] == twice[name]["next"]
    missing = [
        (name, target)
        for name, node in once.items()
        if isinstance(node, dict)
        for target in node.get("next") or []
        if target not in once
    ]
    assert missing == []


def test_retention_overrides_only_apply_to_level_ad_task() -> None:
    """普通广告任务（DailyAdFlow 新流程）不走旧 pipeline，覆盖只在等级广告启动时注入。"""
    data = raw_pipeline()
    assert "LevelAdRetentionContinue" not in data
