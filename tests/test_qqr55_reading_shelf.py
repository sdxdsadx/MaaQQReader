"""QQR-55：书城排行榜页不能被确认成书架；确认不了书架时不当成白名单拒绝。

真实 OCR 帧来自 2026-09-27 第一轮阅读失败现场（``tests/fixtures/autoread_shelf_frames.json``）：
05:50:12 的书城排行榜页含活动横幅「勋章/装扮限时返场」，旧判据子串「章/」
把它误判成书架，随后书架白名单找不到《宇智波》而 exit 3。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Tuple

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import auto_read_30min as arm  # noqa: E402

FRAMES = json.loads(
    (Path(__file__).parent / "fixtures" / "autoread_shelf_frames.json").read_text(encoding="utf-8")
)
Box = Tuple[int, int, int, int]


def frame(name: str) -> List[Tuple[str, Box]]:
    return [(text, tuple(box)) for text, box in FRAMES[name]["boxes"]]


BOOKSTORE = frame("bookstore_ranking_with_medal_banner")
SHELF = frame("shelf")
SHELF_WITHOUT_TARGET = [item for item in SHELF if "宇智波" not in item[0]]


class _Shot:
    def save(self, path: Path) -> Path:
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\nfake")
        return Path(path)


class _Result:
    def __init__(self, boxes):
        self._boxes = boxes

    def text_boxes(self):
        return list(self._boxes)


class _Client:
    def __init__(self, frames):
        self.frames = list(frames)
        self.index = 0

    def screencap(self):
        return _Shot()

    def recognize(self, kind, options, shot):
        boxes = self.frames[min(self.index, len(self.frames) - 1)]
        self.index += 1
        return _Result(boxes)


@pytest.fixture
def device(monkeypatch, tmp_path):
    """替换模块级 Maa 客户端与 adb 动作，记录点击/返回和日志。"""
    taps: List[Tuple[int, int]] = []
    backs: List[int] = []
    logs: List[str] = []
    monkeypatch.setattr(arm, "tap", lambda x, y: taps.append((x, y)))
    monkeypatch.setattr(arm, "press_back", lambda: backs.append(1))
    monkeypatch.setattr(arm, "log", logs.append)
    monkeypatch.setattr(arm, "return_to_capturable", lambda max_backs=6: None)
    monkeypatch.setattr(arm, "dismiss_blocking_dialogs", lambda: 0)
    monkeypatch.setattr(arm.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(arm, "_evidence_dir", tmp_path)

    def install(frames):
        monkeypatch.setattr(arm, "_client", _Client(frames))

    return install, taps, backs, logs


def test_real_bookstore_ranking_page_is_not_shelf() -> None:
    assert arm.classify_page(BOOKSTORE) == "书城"


def test_real_shelf_page_is_shelf() -> None:
    assert arm.classify_page(SHELF) == "书架"


def test_medal_banner_is_not_a_reading_progress_line() -> None:
    assert not arm.SHELF_PROGRESS_PATTERN.search("勋章/装扮限时返场")
    assert arm.SHELF_PROGRESS_PATTERN.search("84章/372章")
    assert arm.SHELF_PROGRESS_PATTERN.search("25章/543章·更新至第529章 物理")


def test_is_on_shelf_rejects_the_failing_frame(device) -> None:
    install, *_ = device
    install([BOOKSTORE])
    assert arm.is_on_shelf() is False


def test_bookstore_goes_to_shelf_tab_then_confirms_target(device) -> None:
    install, taps, backs, logs = device
    # 确认①书城 → 回书架：②书城 → 点书架 tab → ③书架 → 确认②④书架 + 白名单书
    install([BOOKSTORE, BOOKSTORE, SHELF, SHELF])
    why = arm.confirm_allowed_book_on_shelf()
    assert "宇智波：从扉间人柱力开始" in why
    assert taps == [(89, 1263)]  # 只点了书架 tab，没有点任何书
    assert backs == []


def test_confirmed_shelf_without_target_is_whitelist_rejection(device) -> None:
    install, taps, _backs, logs = device
    install([SHELF_WITHOUT_TARGET])
    with pytest.raises(arm.BookNotAllowed):
        arm.confirm_allowed_book_on_shelf()
    assert taps == []
    evidence = [line for line in logs if line.startswith("现场记录")]
    assert evidence and "页面类型=书架" in evidence[0] and "全职法师" in evidence[0]


def test_unconfirmable_shelf_is_not_reported_as_whitelist_rejection(device, tmp_path) -> None:
    install, taps, _backs, logs = device
    install([BOOKSTORE])
    with pytest.raises(RuntimeError) as excinfo:
        arm.confirm_allowed_book_on_shelf(attempts=2)
    assert not isinstance(excinfo.value, arm.BookNotAllowed)
    assert "最后页面：书城" in str(excinfo.value)
    assert all(tap == (89, 1263) for tap in taps)  # 从不点书
    assert any("页面类型=书城" in line and "排行榜" in line for line in logs)
    assert list((tmp_path / "auto_read").glob("*_书城.png"))


def test_rank_subpage_without_bottom_tab_is_not_blind_tapped(device) -> None:
    """2026-09-27 实机：排行榜二级页没有底部导航，不能按固定坐标点「书架」。"""
    handoff_frames = json.loads(
        (Path(__file__).parent / "fixtures" / "handoff_ocr_frames.json").read_text(encoding="utf-8")
    )
    rank = [(text, tuple(box)) for text, box in handoff_frames["rank_subpage"]["boxes"]]
    install, taps, _backs, logs = device
    install([rank])
    assert arm.go_to_shelf_tab() is False
    assert taps == []
    assert any("未看到底部「书架」tab" in line for line in logs)


def _handoff_frame(name: str) -> List[Tuple[str, Box]]:
    data = json.loads(
        (Path(__file__).parent / "fixtures" / "handoff_ocr_frames.json").read_text(encoding="utf-8")
    )
    return [(text, tuple(box)) for text, box in data[name]["boxes"]]


def test_bookstore_banner_is_not_an_activity_dialog(monkeypatch) -> None:
    """2026-09-27 实机：书城横幅「勋章/装扮限时返场」「免费读一年」不是弹窗，不能盲点。"""
    taps: List[Tuple[int, int]] = []
    monkeypatch.setattr(arm, "tap", lambda x, y: taps.append((x, y)))
    monkeypatch.setattr(arm, "log", lambda message: None)
    monkeypatch.setattr(arm.time, "sleep", lambda seconds: None)
    assert any("限时返场" in text for text, _ in BOOKSTORE)
    monkeypatch.setattr(arm, "_client", _Client([BOOKSTORE]))
    assert arm.dismiss_blocking_dialogs() == 0
    assert taps == []


def test_upgrade_dialog_over_bookstore_taps_cancel_first(monkeypatch) -> None:
    taps: List[Tuple[int, int]] = []
    monkeypatch.setattr(arm, "tap", lambda x, y: taps.append((x, y)))
    monkeypatch.setattr(arm, "log", lambda message: None)
    monkeypatch.setattr(arm.time, "sleep", lambda seconds: None)
    dialog = _handoff_frame("bookstore_upgrade_dialog") + [("X", (650, 60, 30, 30))]
    monkeypatch.setattr(arm, "_client", _Client([dialog, BOOKSTORE]))
    assert arm.dismiss_blocking_dialogs() == 1
    assert taps == [(538, 1242)]  # 「取消」(510,1226,56,32)，不是页面上的 X
