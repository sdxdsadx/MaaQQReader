"""书源守门回归：自动阅读只允许白名单书目（issue #17）。

判定依据：**书架上 OCR 到的书名**。不是正文页顶部 OCR（正文页顶部只显示章标题，
用它判定会把正确的《宇智波：从扉间人柱力开始》误判成"不在白名单"，2026-09-15 实测），
也不是封面模板（`reading_target_uchiha_cover.png` 实测是正文页空白截图，恒不命中，
2026-09-21 实测）。

2026-09-21 真机取到的书架 OCR 关键框：
    '宇智波：从扉间人柱力开始' box=(138, 590, 310, 27)
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import auto_read_30min as arm
from auto_read_30min import (
    ALLOWED_BOOK_KEYWORDS,
    NON_SHELF_MARKERS,
    SHELF_ONLY_MARKERS,
    _verify_book_allowed,
    locate_allowed_book_ui,
)


class _FakeOcrResult:
    def __init__(self, boxes):
        self._boxes = boxes

    def text_boxes(self):
        return list(self._boxes)


class _FakeClient:
    """只实现 OCR 路径（截图 + OCR）。"""

    def __init__(self, boxes):
        self._boxes = boxes
        self.calls = 0

    def screencap(self):
        return object()

    def recognize(self, kind, options, screenshot):
        self.calls += 1
        assert kind == "OCR", f"现在只应走 OCR，收到 {kind}"
        return _FakeOcrResult(self._boxes)


def _with_client(boxes):
    """把 fake client 注入模块级 `_client`，并在用例结束后还原。"""
    import pytest  # noqa: F401  (仅用于 fixture 语义，此处手工还原)

    class _Ctx:
        def __enter__(self):
            self._old = arm._client
            arm._client = _FakeClient(boxes)
            return arm._client

        def __exit__(self, *exc):
            arm._client = self._old
            return False

    return _Ctx()


# 真机取到的书架 OCR 快照（节选）
REAL_SHELF_BOXES = [
    ("2:02", (7, 5, 49, 24)),
    ("书架", (27, 45, 105, 43)),
    ("本周未开始阅读", (58, 149, 185, 28)),
    ("我的笔记", (133, 302, 111, 34)),
    ("全职法师", (135, 444, 109, 33)),
    ("宇智波：从扉间人柱力开始", (138, 590, 310, 27)),
    ("84章/372章", (136, 630, 104, 23)),
    ("下班，然后变成魔法少女", (141, 732, 282, 28)),
]


def test_whitelist_constant_is_configurable():
    assert ALLOWED_BOOK_KEYWORDS == ("宇智波",)


def test_shelf_only_markers_exclude_bottom_tab():
    """回归：书架判据不得依赖「书架」二字 —— 底部 tab 在所有页面都有它。

    2026-09-21 实测踩过：流程卡在「广场」（社区书评页），底部导航栏照样有
    「书架」tab，导致 `is_on_shelf()` 误判成功，是书源校验才把它拦下的。
    """
    assert "书架" not in SHELF_ONLY_MARKERS
    assert "广场" in NON_SHELF_MARKERS
    assert "关注" in NON_SHELF_MARKERS


def test_is_on_shelf_rejects_plaza_page():
    """广场页即使有底部「书架」tab，也必须判为不在书架。"""
    plaza_boxes = [
        ("关注", (30, 45, 80, 40)),
        ("广场", (110, 45, 80, 40)),
        ("一键三连", (150, 100, 200, 30)),
        ("热门话题", (40, 800, 150, 35)),
        ("书架", (27, 1270, 105, 40)),  # 底部 tab，所有页面都有
    ]
    with _with_client(plaza_boxes):
        assert arm.is_on_shelf() is False


def test_is_on_shelf_accepts_real_shelf():
    """真机书架页快照 → 判为在书架。"""
    with _with_client(REAL_SHELF_BOXES):
        assert arm.is_on_shelf() is True


def test_real_shelf_snapshot_is_accepted():
    """真机书架 OCR 快照 → 命中《宇智波：从扉间人柱力开始》并给出可点击 box。"""
    with _with_client(REAL_SHELF_BOXES):
        box, message = locate_allowed_book_ui()

    assert box == (138, 590, 310, 27), "应返回书名的真实 box，供点击使用"
    assert "宇智波：从扉间人柱力开始" in message


def test_whitelisted_book_is_allowed_and_box_clickable():
    """白名单书目放行，且返回的 box 中心落在书名行内。"""
    with _with_client(REAL_SHELF_BOXES):
        allowed, message = _verify_book_allowed()

    assert allowed is True
    assert "宇智波" in message


def test_other_book_is_rejected():
    """书架上没有《宇智波》（只有《全职法师》）→ 拒绝，不得静默继续。"""
    boxes = [
        ("书架", (27, 45, 105, 43)),
        ("全职法师", (135, 444, 109, 33)),
        ("457章/3385章", (136, 486, 126, 23)),
    ]
    with _with_client(boxes):
        allowed, message = _verify_book_allowed()

    assert allowed is False
    assert "当前书不在自动阅读白名单" in message
    assert "全职法师" in message


def test_readable_but_non_whitelisted_page_is_rejected():
    """读到了文本但无白名单书名（如奖励页/AI 朗读页）→ 拒绝。"""
    boxes = [("使用你的专属声音读小说", (60, 600, 600, 40))]
    with _with_client(boxes):
        allowed, message = _verify_book_allowed()

    assert allowed is False
    assert "当前书不在自动阅读白名单" in message
    assert "使用你的专属声音读小说" in message


def test_unreadable_shelf_is_rejected():
    """OCR 什么都没读到 → 拒绝，且理由可读。"""
    with _with_client([]):
        allowed, message = _verify_book_allowed()

    assert allowed is False
    assert "OCR 未读到任何文本" in message


def test_no_template_dependency():
    """回归：不得再依赖已废弃的封面模板常量。"""
    assert not hasattr(arm, "TARGET_COVER_TEMPLATE")
