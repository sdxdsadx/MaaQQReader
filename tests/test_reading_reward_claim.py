import json
from pathlib import Path

import pytest

from qqreader.tasks.reading_reward import (
    parse_coin_total,
    reading_claim_buttons,
    reading_rewards_complete,
)


def test_reading_claim_buttons_are_limited_to_reading_card():
    boxes = (
        ("每日阅读领赠币", (60, 360, 220, 40)),
        ("领取", (190, 580, 70, 35)),
        ("立即领取", (470, 580, 120, 35)),
        ("每日听书30分钟+20赠币", (60, 800, 300, 40)),
        ("立即领取", (520, 820, 120, 35)),
    )

    assert reading_claim_buttons(boxes) == boxes[1:3]


def test_reading_card_accepts_logged_ocr_misread_without_claiming_other_card():
    # 2026-09-25 21:13:21~37 的 Maa OCR 持续把“赠币”识别为“赠市”。
    boxes = (
        ("今日已获赠币10", (38, 164, 222, 40)),
        ("每日阅读领赠市", (58, 953, 159, 27)),
        ("今日任务已完成", (58, 984, 139, 26)),
        ("领取", (197, 1176, 37, 21)),
        ("领取", (483, 1176, 37, 21)),
        ("每日听书30分钟+20赠币", (58, 1220, 250, 27)),
        ("立即领取", (520, 1260, 80, 21)),
    )
    assert reading_claim_buttons(boxes) == boxes[3:5]


def test_complete_requires_reading_card_claim_evidence():
    boxes = (
        ("每日阅读领赠币", (60, 360, 220, 40)),
        ("今日任务已完成", (60, 400, 220, 40)),
        ("已领取", (190, 580, 70, 35)),
        ("已领取", (470, 580, 70, 35)),
        ("每日听书30分钟+20赠币", (60, 800, 300, 40)),
    )

    assert reading_rewards_complete(boxes) is True


def test_coin_total_is_parsed():
    assert parse_coin_total((("今日已获赠币254", (0, 0, 1, 1)),)) == 254


class _Shot:
    def save(self, path):
        from pathlib import Path

        Path(path).write_bytes(b"png")


class _SyncDelayClient:
    """前两次看到的阅读卡还不可领，刷新后两档变为“领取”，领取后显示已领取。"""

    NOT_READY = (
        ("今日已获赠币10", (40, 170, 200, 40)),
        ("每日阅读领赠币", (60, 950, 220, 40)),
        ("去阅读", (540, 960, 100, 40)),
        ("10分钟", (190, 1150, 70, 25)),
        ("30分钟", (470, 1150, 70, 25)),
    )
    READY = (
        ("今日已获赠币10", (40, 170, 200, 40)),
        ("每日阅读领赠币", (60, 950, 220, 40)),
        ("领取", (180, 1178, 70, 35)),
        ("领取", (465, 1178, 70, 35)),
    )
    DONE = (
        ("今日已获赠币50", (40, 170, 200, 40)),
        ("每日阅读领赠币", (60, 950, 220, 40)),
        ("今日已领40赠币", (60, 990, 220, 30)),
        ("已领取", (180, 1178, 70, 35)),
        ("已领取", (465, 1178, 70, 35)),
    )

    def __init__(self):
        self.refreshes = 0
        self.clicks = []

    def start_app(self, _package):
        return True

    def screencap(self):
        return _Shot()

    def recognize(self, *_args):
        if self.clicks:
            boxes = self.DONE
        elif self.refreshes >= 2:
            boxes = self.READY
        else:
            boxes = self.NOT_READY
        return type("R", (), {"text_boxes": lambda _self: boxes})()

    def click_key(self, key):
        if key == 4:
            self.refreshes += 1

    def click(self, x, y):
        self.clicks.append((x, y))
        return True

    def swipe(self, *_args):
        return True


def test_claim_waits_for_reading_time_sync_before_failing(monkeypatch, tmp_path):
    import qqreader.tasks.reading_reward as module

    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    client = _SyncDelayClient()

    result = module.claim_reading_rewards(client, tmp_path, sync_wait_seconds=0)

    assert result.succeeded is True
    assert client.refreshes == 2
    assert client.clicks
    assert list(tmp_path.glob("reading_reward_claim_before_*.png"))


def test_claim_completes_when_logged_card_title_is_misread(monkeypatch, tmp_path):
    import qqreader.tasks.reading_reward as module

    class _MisreadClient(_SyncDelayClient):
        NOT_READY = tuple(
            (text.replace("每日阅读领赠币", "每日阅读领赠市"), box)
            for text, box in _SyncDelayClient.NOT_READY
        )
        READY = tuple(
            (text.replace("每日阅读领赠币", "每日阅读领赠市"), box)
            for text, box in _SyncDelayClient.READY
        )
        DONE = tuple(
            (text.replace("每日阅读领赠币", "每日阅读领赠市"), box)
            for text, box in _SyncDelayClient.DONE
        )

    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    client = _MisreadClient()
    result = module.claim_reading_rewards(client, tmp_path, sync_wait_seconds=0)

    assert result.succeeded is True
    assert client.refreshes == 2
    assert client.clicks
    assert result.after_coins == 50


# ---- 进入奖励页：点击入口后页面加载中不能按返回（2026-10-06 实机 mfa_20261006_205809_33602f6e） ----
# 合并 codex/reading-game-log-fix-20261004 后，_open_reward_page 改走统一导航
# goto_reward_page：未知页（加载中）只等待重拍、不盲返；入口优先点时长卡右侧按钮。

_OPEN_FRAMES = json.loads(
    (Path(__file__).parent / "fixtures" / "reading_reward_open_frames.json").read_text(
        encoding="utf-8"
    )
)


def _frame(entry):
    return tuple((text, tuple(box)) for text, box in entry["boxes"])


SHELF = _frame(_OPEN_FRAMES["shelf"])
LOADING = tuple(_frame(item) for item in _OPEN_FRAMES["loading"])
REWARD = _frame(_OPEN_FRAMES["reward"])
# 书架时长卡右侧按钮「领360赠币」(541,166,100,28) 的中心。
ENTRY_CENTER = (541 + 100 // 2, 166 + 28 // 2)


class _FrameClient:
    """按顺序返回真实 OCR 帧；帧用完后重复最后一帧。记录点击、按键和截图序号。"""

    def __init__(self, frames):
        self.frames = list(frames)
        self.index = 0
        self.events = []
        self.current = None

    def start_app(self, _package):
        return True

    def screencap(self):
        self.current = self.frames[min(self.index, len(self.frames) - 1)]
        self.index += 1
        self.events.append(("shot",))
        return _Shot()

    def recognize(self, *_args):
        boxes = self.current
        return type("R", (), {"text_boxes": lambda _self: boxes})()

    def click_key(self, key):
        self.events.append(("key", key))

    def click(self, x, y):
        self.events.append(("click", x, y))
        return True

    def swipe(self, *_args):
        return True

    def clicks(self):
        return [event[1:] for event in self.events if event[0] == "click"]

    def backs(self):
        return [event for event in self.events if event == ("key", 4)]


@pytest.fixture
def no_sleep(monkeypatch):
    import qqreader.tasks.reading_reward as module

    slept = []
    monkeypatch.setattr(module.time, "sleep", lambda seconds: slept.append(seconds))
    return slept


def test_open_reward_page_waits_while_page_loading(no_sleep):
    from qqreader.tasks.reading_reward import _open_reward_page

    client = _FrameClient([SHELF, LOADING[0], LOADING[1], LOADING[2], LOADING[0], REWARD])

    boxes = _open_reward_page(client)

    assert boxes == REWARD
    assert client.clicks() == [ENTRY_CENTER]
    assert client.backs() == []


def test_open_reward_page_reclicks_when_still_on_shelf(no_sleep):
    from qqreader.tasks.reading_reward import _open_reward_page

    # 点击后书架一直在：1.5/3.0/4.5 秒的书架帧不算“点击没生效”（页面可能还在切换），
    # 6.0 秒仍是书架才重点。
    client = _FrameClient([SHELF, SHELF, SHELF, SHELF, SHELF, LOADING[0], REWARD])

    boxes = _open_reward_page(client)

    assert boxes == REWARD
    assert client.clicks() == [ENTRY_CENTER, ENTRY_CENTER]
    assert client.backs() == []


def test_open_reward_page_never_backs_on_loading_frames(no_sleep):
    import qqreader.tasks.reading_reward as module

    # 点击后一直是加载中帧：统一导航只等待，不按返回取消加载；预算用完才报错。
    client = _FrameClient([SHELF, *LOADING])

    with pytest.raises(RuntimeError, match="无法从当前页面进入阅读奖励页"):
        module._open_reward_page(client)

    assert client.backs() == []
    assert client.clicks() == [ENTRY_CENTER]


def test_open_reward_page_shelf_seen_briefly_then_loads_clicks_once(no_sleep):
    from qqreader.tasks.reading_reward import _open_reward_page

    # 点击后第一次轮询（约 1.5 秒）书架还在，随后开始加载：不能重点，否则会打开两层奖励页。
    client = _FrameClient([SHELF, SHELF, LOADING[0], LOADING[1], REWARD])

    boxes = _open_reward_page(client)

    assert boxes == REWARD
    assert client.clicks() == [ENTRY_CENTER]
    assert client.backs() == []


def test_open_reward_page_waits_unknown_start_without_back(no_sleep):
    from qqreader.tasks.reading_reward import _open_reward_page

    # 起点先是 6 帧加载中（未知页），随后出现书架：不盲返，等到书架后点一次入口。
    client = _FrameClient([*([LOADING[0]] * 6), SHELF, REWARD])

    boxes = _open_reward_page(client)

    assert boxes == REWARD
    assert client.clicks() == [ENTRY_CENTER]
    assert client.backs() == []
