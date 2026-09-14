"""issue #15：统一奖励页导航与滑块截图编码回归。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Mapping, Sequence, Tuple

import numpy as np

from qqreader.captcha import slide
from qqreader.maa import RecoResult
from qqreader.reward.nav import back_to_reward, find_watch_entry, goto_reward_page

Box = Tuple[int, int, int, int]
Frame = Sequence[Tuple[str, Box]]
PNG_HEADER = b"\x89PNG\r\n\x1a\n"


class FakeShot:
    def __init__(self, boxes: Frame, *, saved_png: bytes = PNG_HEADER + b"encoded") -> None:
        self.boxes = list(boxes)
        self.data = b"raw-rgba-is-not-a-png"
        self.saved_png = saved_png
        self.saved_paths: List[Path] = []

    def save(self, path: str) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.saved_png)
        self.saved_paths.append(target)
        return target


class FakeClient:
    def __init__(self, frames: Sequence[Frame]) -> None:
        self.frames = list(frames)
        self.frame_index = 0
        self.clicks: List[Tuple[int, int]] = []
        self.swipes: List[Tuple[int, int, int, int, int]] = []
        self.keys: List[int] = []

    def screencap(self) -> FakeShot:
        index = min(self.frame_index, len(self.frames) - 1)
        self.frame_index += 1
        return FakeShot(self.frames[index])

    def recognize(
        self, reco_type: str, params: Mapping[str, Any], screenshot: FakeShot
    ) -> RecoResult:
        assert reco_type == "OCR"
        return RecoResult(
            "OCR",
            bool(screenshot.boxes),
            detail={
                "all": [
                    {"text": text, "box": list(box), "score": 0.99}
                    for text, box in screenshot.boxes
                ]
            },
        )

    def click(self, x: int, y: int) -> bool:
        self.clicks.append((x, y))
        return True

    def swipe(
        self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300
    ) -> bool:
        self.swipes.append((x1, y1, x2, y2, duration_ms))
        return True

    def click_key(self, keycode: int) -> bool:
        self.keys.append(keycode)
        return True


def test_goto_reward_page_handles_splash_and_intro_ocr_branches() -> None:
    client = FakeClient(
        [
            [("跳过1", (620, 20, 70, 30))],
            [("继续阅读", (500, 1080, 120, 50))],
            [("今日已获赠币160", (220, 60, 280, 50))],
        ]
    )

    assert goto_reward_page(client, settle_seconds=0) is True
    assert client.clicks == [(655, 35), (560, 1105)]
    assert client.keys == []


def test_goto_reward_page_handles_body_bookstore_and_shelf_entry() -> None:
    client = FakeClient(
        [
            [("第39章", (40, 70, 100, 30))],
            [("男生", (20, 30, 50, 30)), ("排行榜", (400, 200, 80, 30))],
            [("书架", (20, 30, 60, 30)), ("时长兑赠币，立即领取", (60, 180, 280, 40))],
            [("看小视频领好礼", (60, 1100, 260, 50))],
        ]
    )

    assert goto_reward_page(client, settle_seconds=0) is True
    assert client.keys == [4]
    assert client.clicks == [(70, 1250), (200, 200)]


def test_goto_reward_page_stops_before_clicking_when_captcha_is_visible() -> None:
    client = FakeClient(
        [[("安全验证", (80, 350, 120, 40)), ("今日已获赠币160", (220, 60, 280, 50))]]
    )

    assert goto_reward_page(client, settle_seconds=0) is False
    assert client.clicks == []
    assert client.keys == []


def test_find_watch_entry_scrolls_until_ocr_box_is_visible() -> None:
    client = FakeClient(
        [
            [("每日阅读领赠币", (50, 200, 200, 40))],
            [("玩游戏领赠币", (50, 500, 200, 40))],
            [("立即观看", (540, 1080, 120, 50))],
        ]
    )

    assert find_watch_entry(client, max_scrolls=4, settle_seconds=0) == (
        "立即观看",
        (540, 1080, 120, 50),
    )
    assert client.swipes == [
        (360, 1150, 360, 400, 500),
        (360, 1150, 360, 400, 500),
    ]


def test_back_to_reward_uses_giveup_then_x_then_back() -> None:
    client = FakeClient(
        [
            [("放弃奖励", (180, 800, 160, 50)), ("今日已获赠币", (200, 50, 200, 40))],
            [("X", (30, 60, 40, 40))],
            [("广告详情", (200, 300, 160, 40))],
            [("今日已获赠币170", (200, 50, 220, 40))],
        ]
    )

    assert back_to_reward(client, settle_seconds=0) is True
    assert client.clicks == [(260, 825), (50, 80)]
    assert client.keys == [4]


def test_live_snap_detects_saved_png_not_raw_screenshot_data(monkeypatch, tmp_path: Path) -> None:
    import scripts.live_captcha_auto as live

    expected_png = PNG_HEADER + b"encoded-by-save"
    shot = FakeShot([("安全验证", (80, 350, 120, 40))], saved_png=expected_png)

    class SnapClient(FakeClient):
        def __init__(self) -> None:
            super().__init__([shot.boxes])

        def screencap(self) -> FakeShot:
            return shot

    seen = []
    monkeypatch.setattr(live, "OUT", tmp_path)
    monkeypatch.setattr(live, "detect_slide", lambda data: seen.append(data) or "detected")

    detection, texts = live.snap(SnapClient(), "fixture")

    assert detection == "detected"
    assert texts == ["安全验证"]
    assert seen == [expected_png]
    assert (tmp_path / "autocap_fixture.png").read_bytes() == expected_png
    assert expected_png != shot.data


def test_detect_slide_accepts_real_captcha_fixture() -> None:
    fixture = (
        Path(__file__).resolve().parents[1]
        / "runtime"
        / "screenshots"
        / "ad_watch"
        / "captcha_now.png"
    )

    detection = slide.detect_slide(fixture.read_bytes())

    assert detection.found is True, detection.error
    assert detection.track == (75, 806, 567, 26)
    assert detection.slider_center == (168, 818)
    assert 120 <= detection.distance <= int(detection.track[2] * 0.9)


def test_gap_detection_falls_back_to_parameterized_slider_offset() -> None:
    # Uniform ROI contains no Otsu contour/Canny edge, so _find_gap_x must take
    # the parameterized slider-right-edge fallback.
    gray = np.zeros((1280, 720), dtype=np.uint8)
    track = (75, 806, 567, 26)
    slider_box = (109, 789, 118, 59)

    gap_x = slide._find_gap_x(
        gray,
        track,
        slider_box,
        fallback_offset_ratio=2.18,
        fallback_min_distance=120,
        fallback_max_distance_ratio=0.9,
    )

    assert gap_x == 484
    assert gap_x - (slider_box[0] + slider_box[2] // 2) == 316
