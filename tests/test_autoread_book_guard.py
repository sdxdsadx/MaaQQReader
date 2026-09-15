from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from auto_read_30min import ALLOWED_BOOK_KEYWORDS, _verify_book_allowed


class _FakeRecognition:
    def __init__(self, boxes):
        self._boxes = boxes

    def text_boxes(self):
        return self._boxes


class _FakeClient:
    def __init__(self, boxes):
        self._boxes = boxes

    def screencap(self):
        return object()

    def recognize(self, kind, options, screenshot):
        assert kind == "OCR"
        assert options == {}
        return _FakeRecognition(self._boxes)


def test_allowed_book_title_is_accepted():
    client = _FakeClient([("宇智波：从扉间人柱力开始", (145, 42, 430, 40))])

    allowed, message = _verify_book_allowed(client)

    assert ALLOWED_BOOK_KEYWORDS == ("宇智波",)
    assert allowed is True
    assert "宇智波" in message


def test_other_book_is_rejected_with_readable_error():
    client = _FakeClient([("全职法师", (280, 45, 160, 36))])

    allowed, message = _verify_book_allowed(client)

    assert allowed is False
    assert message == "当前书不在自动阅读白名单: 全职法师"


def test_audiobook_detail_page_is_rejected():
    client = _FakeClient([
        ("AI朗读", (300, 38, 120, 36)),
        ("全职法师", (250, 82, 220, 38)),
        ("播放", (320, 600, 80, 40)),
    ])

    allowed, message = _verify_book_allowed(client)

    assert allowed is False
    assert message.startswith("当前书不在自动阅读白名单: ")
    assert "全职法师" in message
