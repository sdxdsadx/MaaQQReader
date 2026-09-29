"""每日弹窗遮挡书架 / 奖励页（2026-09-28 每日运行 daily_20260928_233026_1486afea）。

全部用例使用 ``tests/fixtures/daily_popup_ocr_frames.json`` 中的真实 OCR 帧
（从 ``runtime/logs/maafw*.log`` 的 OCRer 结果原样抽取，来源写在 source 字段）：

* 00:02 跨天后书架弹出「双倍月票开启 / 秋日豪礼开抢 / 立即参与」海报，下方单独
  一个 X。自动阅读第 3 段判“书架上没有白名单书目”退出；交接检查把它判成书架；
  游戏在遮罩下空点 35 分钟超时；广告、等级广告随后失败。
* 当天第一次进奖励页弹出「签到成功，获得10赠币 / 我知道了」，外部 App 任务在
  弹窗上空滑 40 秒后失败。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, List, Mapping, Sequence, Tuple

import pytest

from qqreader.maa import RecoResult
from qqreader.page.blocking_popup import find_blocking_popup
from qqreader.page.feature_keys import DEFAULT_FEATURE_KEYS
from qqreader.page.observation import PageObservation
from qqreader.page.states import Orientation, PageState, RunState
from qqreader.reward.nav import find_watch_entry, goto_reward_page
from qqreader.runner.handoff import FrameKind, HandoffVerdict, check_handoff, classify_frame
from qqreader.tasks import Action, GameTaskAdapter, feature_key
from qqreader.tasks.game import build_game_action_plan
from tests.helpers import QQ, SimulatedDevice, make_context, make_recognizer

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import auto_read_30min as arm  # noqa: E402

Box = Tuple[int, int, int, int]
Frame = List[Tuple[str, Box]]
FRAMES = json.loads(
    (Path(__file__).parent / "fixtures" / "daily_popup_ocr_frames.json").read_text(encoding="utf-8")
)
KEYS = DEFAULT_FEATURE_KEYS


def frame(name: str) -> Frame:
    return [(text, tuple(box)) for text, box in FRAMES[name]["boxes"]]


PROMO = frame("shelf_promo_popup")
CHECKIN = frame("reward_checkin_popup")
SHELF = frame("shelf_after_popup_closed")
REWARD = frame("reward_page_plain")
PROMO_X = (358, 946)
CHECKIN_OK = (357, 764)


class FakeShot:
    def __init__(self, boxes: Frame) -> None:
        self.boxes = boxes

    def save(self, path) -> Path:
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\nfake")
        return Path(path)


class FakeClient:
    def __init__(self, frames: Sequence[Frame]) -> None:
        self.frames = list(frames)
        self.index = 0
        self.clicks: List[Tuple[int, int]] = []
        self.keys: List[int] = []
        self.swipes: List[Tuple[int, ...]] = []

    def screencap(self) -> FakeShot:
        shot = FakeShot(self.frames[min(self.index, len(self.frames) - 1)])
        self.index += 1
        return shot

    def recognize(self, reco_type: str, params: Mapping[str, Any], shot: FakeShot) -> RecoResult:
        assert reco_type == "OCR"
        return RecoResult(
            "OCR",
            bool(shot.boxes),
            detail={"all": [{"text": t, "box": list(b), "score": 0.99} for t, b in shot.boxes]},
        )

    def click(self, x: int, y: int) -> bool:
        self.clicks.append((x, y))
        return True

    def click_key(self, keycode: int) -> bool:
        self.keys.append(keycode)
        return True

    def swipe(self, *args: int) -> bool:
        self.swipes.append(args)
        return True

    def stop_app(self, package: str) -> bool:
        return True

    def start_app(self, package: str) -> bool:
        return True


# ------------------------------------------------------------------ 识别


def test_detects_shelf_promo_popup_close_by_layout() -> None:
    assert find_blocking_popup(PROMO) == ("X", PROMO_X)


def test_detects_reward_checkin_popup_and_prefers_acknowledge_button() -> None:
    # 不点「看视频额外领」（会打开广告），也不点同帧下方的 X。
    assert find_blocking_popup(CHECKIN) == ("我知道了", CHECKIN_OK)


@pytest.mark.parametrize(
    "name",
    [
        "shelf_after_popup_closed",
        "reward_page_plain",
        # 同一活动以横幅出现在书城页，不是弹窗。
        "bookstore_banner_same_campaign",
        # 奖励页偏离中线的 X（性质未确认），保守不点。
        "reward_page_offcenter_x",
    ],
)
def test_plain_pages_are_not_blocking_popups(name: str) -> None:
    assert find_blocking_popup(frame(name)) is None


# ------------------------------------------------------------------ 交接检查


def test_handoff_does_not_accept_shelf_behind_popup() -> None:
    assert classify_frame(PROMO) is FrameKind.BLOCKING_POPUP
    assert classify_frame(SHELF) is FrameKind.SHELF


def test_handoff_closes_popup_then_confirms_shelf() -> None:
    client = FakeClient([PROMO, SHELF])
    result = check_handoff(client, package=QQ, settle_seconds=0, restart_wait_seconds=0)
    assert result.verdict is HandoffVerdict.READY
    assert client.clicks == [PROMO_X]
    assert client.keys == []


# ------------------------------------------------------------------ 自动阅读


@pytest.fixture
def reader(monkeypatch, tmp_path):
    taps: List[Tuple[int, int]] = []
    monkeypatch.setattr(arm, "tap", lambda x, y: taps.append((x, y)))
    monkeypatch.setattr(arm, "press_back", lambda: None)
    monkeypatch.setattr(arm, "log", lambda message: None)
    monkeypatch.setattr(arm, "return_to_capturable", lambda max_backs=6: None)
    monkeypatch.setattr(arm.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(arm, "_evidence_dir", tmp_path)
    monkeypatch.setattr(arm, "_allowed_keywords", ("宇智波",))

    def install(frames):
        monkeypatch.setattr(arm, "_client", FakeClient(frames))
        return taps

    return install


def test_autoread_does_not_treat_popup_covered_shelf_as_shelf() -> None:
    assert arm.classify_page(PROMO) != "书架"


def test_autoread_closes_popup_instead_of_rejecting_whitelist(reader) -> None:
    # 第 1 帧判页面、第 2 帧是关弹窗前重新截的图，之后弹窗已关闭。
    taps = reader([PROMO, PROMO, SHELF, SHELF, SHELF])
    why = arm.confirm_allowed_book_on_shelf()
    assert "宇智波" in why
    assert taps[0] == PROMO_X


# ------------------------------------------------------------------ 奖励页导航


def test_goto_reward_page_closes_shelf_popup_and_checkin_popup() -> None:
    client = FakeClient([PROMO, SHELF, CHECKIN, REWARD])
    assert goto_reward_page(client, settle_seconds=0) is True
    assert client.clicks[0] == PROMO_X
    assert client.clicks[-1] == CHECKIN_OK
    assert len(client.clicks) == 3  # X → 书架领币入口 → 我知道了
    assert client.index == 4  # 关掉签到弹窗后重新截图确认奖励页


def test_find_watch_entry_closes_checkin_popup_before_scrolling() -> None:
    client = FakeClient([CHECKIN, REWARD + [("立即观看", (540, 1080, 120, 50))]])
    assert find_watch_entry(client, max_scrolls=2, settle_seconds=0) == (
        "立即观看",
        (540, 1080, 120, 50),
    )
    assert client.clicks == [CHECKIN_OK]
    assert client.swipes == []


# ------------------------------------------------------------------ 游戏任务


def _game_adapter(device: SimulatedDevice, client: FakeClient) -> GameTaskAdapter:
    return GameTaskAdapter(
        game_duration_seconds=60.0,
        exit_action=Action.tap_point(695, 302),
        device=device,
        plan=build_game_action_plan(KEYS),
        expected_package=KEYS.qq_reader_package,
        popup_feature=feature_key(KEYS, KEYS.popup_close),
        navigation_client=client,
    )


def _context(boxes: Frame):
    observation = PageObservation(
        current_app=QQ,
        orientation=Orientation.PORTRAIT,
        ocr_texts=tuple(text for text, _ in boxes),
    )
    return make_context(observation, run_state=RunState.RUNNING)


@pytest.mark.parametrize(
    "boxes,point", [(PROMO, PROMO_X), (CHECKIN, CHECKIN_OK)], ids=["shelf_promo", "checkin"]
)
def test_game_closes_blocking_popup_instead_of_tapping_under_mask(boxes, point) -> None:
    device = SimulatedDevice()
    client = FakeClient([boxes])
    context = _context(boxes)
    assert context.state in (PageState.HOME, PageState.REWARD_HOME)
    step = _game_adapter(device, client).advance(context)
    assert step.progress
    assert client.clicks == [point]
    assert device.calls == []


def test_game_stops_retapping_popup_that_does_not_close() -> None:
    device = SimulatedDevice()
    client = FakeClient([PROMO])
    adapter = _game_adapter(device, client)
    context = _context(PROMO)
    for _ in range(5):
        adapter.advance(context)
    assert client.clicks == [PROMO_X] * 3


def test_autoread_cancels_upgrade_dialog_before_popup_below_it(reader) -> None:
    # 2026-09-24 真实帧：升级提示叠在「中秋找玉兔」海报上，必须先点升级提示的「取消」。
    stacked = [
        ("安装新版本", (238, 1150, 244, 36)),
        ("已下载新版本，是否安装？", (180, 1100, 360, 30)),
        ("取消", (500, 1226, 56, 31)),
    ] + PROMO
    taps = reader([stacked, SHELF])
    arm.dismiss_blocking_dialogs()
    assert taps[0] == (528, 1241)


# ------------------------------------------------------------------ 外部 App（旧 pipeline）

#: 旧 pipeline 中外部 App 前段的真实节点结构（_backup_old_project_*/assets/resource/
#: pipeline/qq_reader_trial.json，2026-09-29 摘录）。
EXTERNAL_PIPELINE = {
    "DailyExternalAppFlow": {"action": "StartApp", "package": "com.qq.reader", "next": [
        "ExternalBothComplete", "ExternalRewardPageReady", "ExternalOpenRewardFromShelf",
        "ExternalBackUntilRewardOrShelf"]},
    "ExternalBackUntilRewardOrShelf": {"action": "ClickKey", "key": 4, "next": [
        "ExternalBothComplete", "ExternalRewardPageReady", "ExternalOpenRewardFromShelf",
        "ExternalBackUntilRewardOrShelf"]},
    "ExternalOpenRewardFromShelf": {"recognition": "OCR", "expected": "领\d+赠币|签到领赠币",
        "action": "Click", "next": [
        "ExternalBothComplete", "ExternalRewardPageReady", "ExternalScrollToDianping"]},
    "ExternalRewardPageReady": {"recognition": "OCR", "expected": "今日已获赠币", "next": [
        "ExternalBothComplete", "ExternalClickDianping", "ExternalBaiduVisibleAfterDianping",
        "ExternalDianpingRowFound", "ExternalReachedBottom", "ExternalScrollToDianping"]},
    "ExternalScrollToDianping": {"action": "Swipe", "max_hit": 14, "next": [
        "ExternalBothComplete", "ExternalClickDianping", "ExternalBaiduVisibleAfterDianping",
        "ExternalDianpingRowFound", "ExternalScrollToDianping"]},
}


def test_external_pipeline_dismisses_checkin_popup_before_reward_page_nodes(tmp_path) -> None:
    import run_task

    pipeline = tmp_path / "pipeline" / "qq_reader_trial.json"
    pipeline.parent.mkdir()
    original = json.dumps(EXTERNAL_PIPELINE, ensure_ascii=False).encode("utf-8")
    pipeline.write_bytes(original)

    assert run_task._patch_legacy_pipeline(tmp_path, None, None, "DailyExternalAppFlow") == original
    data = json.loads(pipeline.read_text(encoding="utf-8"))
    node = data[run_task.EXTERNAL_CHECKIN_DISMISS_NODE]
    # 「我知道了」的真实 OCR 框必须落在节点 ROI 内。
    label, (x, y, w, h) = next(item for item in CHECKIN if item[0] == "我知道了")
    rx, ry, rw, rh = node["roi"]
    assert rx <= x and x + w <= rx + rw and ry <= y and y + h <= ry + rh
    assert node["action"] == "Click" and node["max_hit"] <= 3
    for name in ("ExternalOpenRewardFromShelf", "ExternalRewardPageReady", "ExternalScrollToDianping"):
        assert data[name]["next"][0] == run_task.EXTERNAL_CHECKIN_DISMISS_NODE
    # 「看视频额外领」会打开广告，不能在 ROI 里。
    _, (vx, vy, vw, vh) = next(item for item in CHECKIN if item[0] == "看视频额外领")
    assert not (ry <= vy and vy + vh <= ry + rh)
