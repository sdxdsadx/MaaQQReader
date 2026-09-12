"""issue #10 回归：GAME_HALL 裸 marker「排行」「分类」被书城页误命中。

书城页 OCR 含「排行榜」，ONE_OF 子串匹配让 GAME_HALL 的 required 特征
（旧 values 含「排行」）命中，叠加 game_app + orientation 后达到
min_matched=2 → 书城页被判成 GAME_HALL（confirmed），随后 advance 执行
游戏任务的 tap_point(360, 360) 点在书城页无效 → observe/tap 死循环，
DailyAdFlow 挂死。

修复：GAME_HALL（以及 GAME_LOADING 降级链，同源收紧）去掉裸「排行」
「分类」「活动」，只保留游戏大厅强锚点（精选大作/今日必玩推荐/新游/
游戏大厅）。

OCR 快照来自 scripts/_diag_r1v3.py（两帧真实设备书城页）。
"""

from __future__ import annotations

from tests.helpers import make_recognizer
from qqreader.page.observation import PageObservation
from qqreader.page.states import Orientation, PageState

# 书城页（男生频道）第一帧：scripts/_diag_r1v3.py
_BOOKSTORE_OCR = (
    "6:09", "男生", "排行榜>", "本周强推", "今日必读", "高分必读",
    "斗罗：先天半", "级，但是唯...", "武魂彩虹龙", "天才对决",
    "麟月成情敌？", "送你31天会员",
)

# 书城页 + 「安装新版本」弹窗第二帧：scripts/_diag_r1v3.py
_BOOKSTORE_POPUP_OCR = (
    "5:53", "男生 女生 出版 会员", "安装新版本", "有奖", "排行榜>", "高分必读",
)

# 真游戏大厅（helpers.game_hall_observation 同源文案）
_GAME_HALL_OCR = ("精选大作", "今日必玩推荐", "排行", "分类", "在线玩")


def _observe(ocr: tuple, *, orientation: Orientation = Orientation.PORTRAIT):
    observation = PageObservation(
        current_app=None,  # 真机 ADB 前台探测可能失败，与诊断脚本保持一致
        orientation=orientation,
        ocr_texts=ocr,
    )
    return make_recognizer().evaluate(observation)


def test_bookstore_page_is_not_game_hall() -> None:
    """书城页「排行榜」不得再被子串误命中成 GAME_HALL。"""
    decision = _observe(_BOOKSTORE_OCR)
    assert decision.state is not PageState.GAME_HALL
    assert not decision.is_confirmed or decision.state is not PageState.GAME_HALL
    candidate = decision.candidate(PageState.GAME_HALL)
    assert candidate is not None
    assert candidate.required_ok is False, (
        "书城页不应满足 GAME_HALL 的 required 特征"
    )


def test_bookstore_page_with_popup_is_not_game_hall() -> None:
    """带「安装新版本」弹窗的书城页同样不得判成 GAME_HALL。"""
    decision = _observe(_BOOKSTORE_POPUP_OCR)
    assert decision.state is not PageState.GAME_HALL
    candidate = decision.candidate(PageState.GAME_HALL)
    assert candidate is not None
    assert candidate.required_ok is False


def test_bookstore_page_does_not_slide_into_game_loading() -> None:
    """GAME_LOADING 降级链曾含同组裸 marker（「活动/排行/分类」），且其
    orientation 兼容竖屏；书城页同样不得转判成 GAME_LOADING。"""
    for ocr in (_BOOKSTORE_OCR, _BOOKSTORE_POPUP_OCR):
        decision = _observe(ocr)
        assert decision.state is not PageState.GAME_LOADING
        candidate = decision.candidate(PageState.GAME_LOADING)
        assert candidate is not None
        assert candidate.required_ok is False


def test_real_game_hall_still_confirmed() -> None:
    """真游戏大厅 OCR（精选大作/今日必玩推荐/排行/分类/在线玩）仍判 GAME_HALL。"""
    decision = _observe(_GAME_HALL_OCR)
    assert decision.state is PageState.GAME_HALL
    assert decision.is_confirmed


def test_game_hall_strong_anchors_still_match() -> None:
    """收紧后的候选词各自独立可确认 GAME_HALL（不依赖「精选大作」单一锚点）。"""
    for marker in ("今日必玩推荐", "新游", "游戏大厅"):
        decision = _observe((marker, "在线玩"))
        assert decision.state is PageState.GAME_HALL, marker
