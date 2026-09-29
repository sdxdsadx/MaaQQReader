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
import re
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


@pytest.mark.parametrize(
    "name,expected",
    [
        ("shelf_promo_popup", ("X", PROMO_X)),
        # 另外两期不同文案的活动弹窗：规则里没有任何活动文案，同样命中。
        ("shelf_cash_popup_20260927", ("X", (358, 946))),
        ("shelf_midautumn_popup_20260924", ("X", (358, 946))),
        # 关闭类文字优先：点「我知道了」，不点「看视频额外领」，也不点同帧的 X。
        ("reward_checkin_popup", ("我知道了", CHECKIN_OK)),
    ],
)
def test_any_popup_over_main_page_is_closed_by_its_close_button(name, expected) -> None:
    assert find_blocking_popup(frame(name)) == expected


def test_close_text_button_is_preferred_over_glyph() -> None:
    # 真实书架帧 + 一个「关闭」文字按钮（历史日志里还没有这种弹窗的实拍帧）。
    boxes = SHELF + [("关闭", (320, 900, 80, 36)), ("X", (600, 400, 30, 30))]
    assert find_blocking_popup(boxes) == ("关闭", (360, 918))


@pytest.mark.parametrize(
    "name",
    [
        "shelf_after_popup_closed",
        "reward_page_plain",
        # 同一活动以横幅出现在书城页，不是弹窗。
        "bookstore_banner_same_campaign",
        # 奖励页「邀请好友」头像占位被 OCR 成一排 X / x。
        "reward_page_offcenter_x",
        # 听书时书架左下角悬浮播放器的 X：点了会停止听书。
        "shelf_audiobook_mini_player",
        # 验证码只交给 CaptchaGuard。
        "reward_captcha_with_x",
        # 「我的」页不是计划内主页面，它的 X 是页面图标。
        "my_page_with_x",
    ],
)
def test_page_owned_x_is_not_treated_as_popup(name: str) -> None:
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
    node = data[run_task.EXTERNAL_POPUP_DISMISS_NODE]
    assert node["action"] == "Click" and node["max_hit"] <= 3
    for name in ("ExternalOpenRewardFromShelf", "ExternalRewardPageReady", "ExternalScrollToDianping"):
        assert data[name]["next"][0] == run_task.EXTERNAL_POPUP_DISMISS_NODE
    # 用真实签到弹窗帧模拟 Maa OCR 节点：只命中「我知道了」，且在 ROI 内。
    pattern = re.compile(node["expected"])
    rx, ry, rw, rh = node["roi"]
    matched = [
        (text, box) for text, box in CHECKIN
        if pattern.search(text)
        and rx <= box[0] and box[0] + box[2] <= rx + rw and ry <= box[1] and box[1] + box[3] <= ry + rh
    ]
    assert [text for text, _ in matched] == ["我知道了"]
    # 普通奖励页上不命中任何文字。
    assert not [text for text, _ in REWARD if pattern.search(text)]


# ------------------------------------------------------------------ 2026-09-29 实机


def test_live_checkin_popup_20260929_is_closed() -> None:
    assert find_blocking_popup(frame("reward_checkin_popup_20260929")) == ("我知道了", (358, 766))


def test_autoread_does_not_treat_reward_page_as_shelf() -> None:
    # 实机 run daily_20260929_111500_9cb3bb10：关掉签到弹窗后是奖励页，
    # 「今日再读7分钟领20赠币」含「再读」，旧判据把它当书架 → 白名单拒绝 exit 3。
    assert arm.classify_page(frame("reward_page_after_checkin_20260929")) == "奖励页"


def test_autoread_backs_out_of_reward_page_then_finds_book(reader, monkeypatch) -> None:
    popup = frame("reward_checkin_popup_20260929")
    reward = frame("reward_page_after_checkin_20260929")
    state = {"page": "popup", "backs": 0}

    class Device(FakeClient):
        def screencap(self):
            return FakeShot({"popup": popup, "reward": reward, "shelf": SHELF}[state["page"]])

    def tap(x, y):
        if state["page"] == "popup" and (x, y) == (358, 766):
            state["page"] = "reward"

    def back():
        state["backs"] += 1
        if state["page"] == "reward":
            state["page"] = "shelf"

    reader([])
    monkeypatch.setattr(arm, "_client", Device([]))
    monkeypatch.setattr(arm, "tap", tap)
    monkeypatch.setattr(arm, "press_back", back)
    why = arm.confirm_allowed_book_on_shelf()
    assert "宇智波" in why
    assert state["backs"] >= 1


# ------------------------------------------------------------------ 游戏退出后领奖（2026-09-29 实机）

GAME_CLAIMABLE = frame("reward_game_claimable_20260929")
GAME_CLAIM_BUTTON = (592, 611)  # 「玩游戏领赠币+20赠币」同一行的「立即领取」(550,597,85,28)


def test_game_reward_page_with_recharge_row_counts_as_success_page() -> None:
    # 实机 run daily_20260929_111500_9cb3bb10：退出游戏后奖励页被识别成 GAME_ENTRY
    # （「游戏任意充值领赠币 / 去玩游戏」行），成功条件只认 REWARD_HOME → 空转到超时。
    from qqreader.tasks.game import build_game_contract

    context = _context(GAME_CLAIMABLE)
    assert context.state is PageState.GAME_ENTRY
    context.update_data(game_exit_done=True)
    assert build_game_contract().success_condition.evaluate(context).satisfied


def test_game_claims_reward_on_game_row_before_success() -> None:
    from qqreader.tasks.game import build_game_contract

    device = SimulatedDevice()
    claimed = [item for item in GAME_CLAIMABLE if item[0] != "立即领取"] + [("已领取", (560, 597, 70, 28))]
    client = FakeClient([GAME_CLAIMABLE, claimed])
    adapter = _game_adapter(device, client)
    context = _context(GAME_CLAIMABLE)
    context.update_data(game_exit_done=True, game_claim_pending=True, game_coin_baseline=50)
    success = build_game_contract().success_condition
    # 赠币计数 50 → 70 不能代替领取：仍须先点游戏行的「立即领取」。
    assert not success.evaluate(context).satisfied
    step = adapter.advance(context)
    assert client.clicks == [GAME_CLAIM_BUTTON]
    assert step.progress
    context = _context(claimed)
    context.update_data(game_exit_done=True, game_claim_pending=True)
    adapter.advance(context)
    assert client.clicks == [GAME_CLAIM_BUTTON]
    assert success.evaluate(context).satisfied


def test_game_claim_gives_up_after_three_taps() -> None:
    device = SimulatedDevice()
    client = FakeClient([GAME_CLAIMABLE])
    adapter = _game_adapter(device, client)
    context = _context(GAME_CLAIMABLE)
    context.update_data(game_exit_done=True, game_claim_pending=True)
    for _ in range(5):
        adapter.advance(context)
    assert client.clicks == [GAME_CLAIM_BUTTON] * 3
    assert context.get("game_claim_pending") is False


# ------------------------------------------------------------------ 阅读领奖（2026-09-29 实机）


def test_reading_claim_uses_last_readable_coin_total(monkeypatch, tmp_path) -> None:
    """实机 run daily_20260929_123918_ff2993fd：只读 13 分钟，10 分钟档领到（194 → 214），
    30 分钟档按钮是灰的点不动；最后一帧 OCR 把「今日已获赠币」和数字拆开，旧逻辑只看
    最后一帧，读不到数字 → 判“缺少币值证据”失败。"""
    import qqreader.tasks.reading_reward as rr

    before = frame("reading_card_before_claim_20260929")
    claimed = frame("reading_card_after_first_claim_20260929")
    split = frame("reading_card_coin_split_20260929")
    assert rr.parse_coin_total(split) is None
    state = {"page": before}

    class Device(FakeClient):
        def screencap(self):
            return FakeShot(state["page"])

        def click(self, x, y):
            super().click(x, y)
            state["page"] = claimed if (x, y) == (215, 1186) else split

    monkeypatch.setattr(rr.time, "sleep", lambda seconds: None)
    client = Device([])
    result = rr.claim_reading_rewards(client, tmp_path)
    assert result.succeeded, result.reason
    assert (result.before_coins, result.after_coins) == (194, 214)
    assert client.clicks[0] == (215, 1186)
