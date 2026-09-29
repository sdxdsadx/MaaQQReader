"""计划外弹窗识别：盖在书架 / 奖励页 / 书城上的任何弹窗，优先找关闭按钮。

只依赖一帧 OCR 文本框，只返回 OCR 实际看到的按钮中心，不用固定坐标。

背景（2026-09-28 每日运行 ``daily_20260928_233026_1486afea``）：跨天后书架弹出
运营海报，当天第一次进奖励页弹出「签到成功」。弹窗会透出背景页文案，原逻辑
把它当成正常书架 / 奖励页，后续任务在遮罩下空点直到超时。运营弹窗每期都换
样子，所以不按某期文案识别，而是：

1. 背景是计划内主页面（书架 / 奖励页 / 书城，按页面独有文案认）；弹窗几乎
   盖满屏幕、只剩底部导航 tab 时，只认居中的 X（弹窗关闭钮都在中线上，
   「我的」页自带的图标 X 在右侧）；
2. 屏幕中间区域出现关闭类按钮——先找只关闭、无副作用的文字按钮（关闭 /
   我知道了 / 取消 / 以后再说 …），再找单独的 X / ×；
3. 排除页面本身就有的 X（全部用真实 OCR 帧确认过）：
   * 状态栏 / 标题栏（y<120）和底部导航区（y>1150）；
   * 奖励页「邀请好友」一排头像占位：OCR 读成 X / x / +，同一行有多个，
     正下方是「待邀请」；
   * 听书时书架左下角悬浮播放器的 X（实测约 (181,1110,24,26)，同屏有
     「正在播放…」），点了会停止听书。

画面上有验证码时一律返回 ``None``：验证码只交给 CaptchaGuard，不点击。

绝不点「立即参与」「看视频额外领」「立即领取」这类会产生副作用的按钮。
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

Box = Tuple[int, int, int, int]
OcrBox = Tuple[str, Box]
Target = Tuple[str, Tuple[int, int]]

SCREEN_CENTER_X = 360
#: 关闭类文字按钮（整框精确匹配），按优先级排列。只关闭弹窗、不改变账号或环境。
DISMISS_LABELS = (
    "我知道了", "知道了", "关闭", "以后再说", "下次再说", "暂不", "暂不需要",
    "残忍拒绝", "不了", "取消",
)
CLOSE_GLYPHS = frozenset(("X", "x", "×", "✕", "╳"))
#: 弹窗按钮所在的屏幕区域（720×1280 的按钮中心 y）。
POPUP_MIN_Y = 120
POPUP_MAX_Y = 1150

#: 背景是计划内主页面的依据（页面独有文案；底部导航在「我的」等页也有，不能用）。
SHELF_MARKERS = ("签到领赠币", "我的笔记", "时长兑赠币", "本周未开始阅读")
REWARD_MARKERS = (
    "今日已获赠币", "看小视频领好礼", "玩游戏领赠币", "每日阅读领赠币", "签到提醒", "获奖记录",
)
BOOKSTORE_MARKERS = ("男生", "女生", "排行榜", "本周强推", "今日必读", "高分必读")

#: 页面自带 X 的上下文。
INVITE_SLOT_LABELS = ("待邀请",)
INVITE_SLOT_GAP = 90
ROW_TOLERANCE = 20
MINI_PLAYER_MARKERS = ("正在播放",)
#: 悬浮播放器所在的左下角区域（按钮中心 x < 300 且 y > 950）。
MINI_PLAYER_MAX_X = 300
MINI_PLAYER_MIN_Y = 950
#: 底部导航 tab（主 tab 页都有；单独出现时只认居中的 X）。
BOTTOM_NAV_TABS = ("书架", "书城")
BOTTOM_NAV_MIN_Y = 1150
CENTER_TOLERANCE = 40
CAPTCHA_MARKERS = ("安全验证", "拖动下方滑块", "拖动滑块", "滑动验证", "完成拼图")


def _center(box: Box) -> Tuple[int, int]:
    x, y, width, height = box
    return x + width // 2, y + height // 2


def _joined(boxes: Sequence[OcrBox]) -> str:
    return " ".join(text.replace(" ", "") for text, _ in boxes)


def is_planned_main_page(boxes: Sequence[OcrBox]) -> bool:
    """背景是否是书架 / 奖励页 / 书城（弹窗透出的背景文案也算）。"""
    text = _joined(boxes)
    return (
        any(marker in text for marker in SHELF_MARKERS)
        or any(marker in text for marker in REWARD_MARKERS)
        or sum(marker in text for marker in BOOKSTORE_MARKERS) >= 2
    )


def _has_bottom_nav(boxes: Sequence[OcrBox]) -> bool:
    labels = {text.strip() for text, box in boxes if box[1] >= BOTTOM_NAV_MIN_Y}
    return all(tab in labels for tab in BOTTOM_NAV_TABS)


def _in_popup_zone(box: Box) -> bool:
    return POPUP_MIN_Y <= _center(box)[1] <= POPUP_MAX_Y


def _is_page_owned_glyph(box: Box, boxes: Sequence[OcrBox]) -> bool:
    """X 属于页面本身（邀请头像 / 听书悬浮播放器），不是弹窗关闭按钮。"""
    cx, cy = _center(box)
    for text, other in boxes:
        if other is box:
            continue
        label = text.strip()
        # 同一行还有别的 X / + ：邀请好友头像占位。
        if (label in CLOSE_GLYPHS or label == "+") and abs(_center(other)[1] - cy) <= ROW_TOLERANCE:
            return True
        # 正下方是「待邀请」：同上。
        if (
            any(marker in label for marker in INVITE_SLOT_LABELS)
            and 0 < other[1] - box[1] <= INVITE_SLOT_GAP
        ):
            return True
        # 听书中：左下角悬浮播放器的 X。
        if (
            any(marker in label for marker in MINI_PLAYER_MARKERS)
            and cx < MINI_PLAYER_MAX_X
            and cy > MINI_PLAYER_MIN_Y
        ):
            return True
    return False


def find_blocking_popup(boxes: Sequence[OcrBox]) -> Optional[Target]:
    """返回要点的 (按钮文字, 中心点)；背景不是主页面或没有关闭按钮时返回 ``None``。"""
    if not boxes or any(marker in _joined(boxes) for marker in CAPTCHA_MARKERS):
        return None
    if not is_planned_main_page(boxes):
        if not _has_bottom_nav(boxes):
            return None
        # 只剩底部导航：弹窗盖满了背景页，只认居中的 X。
        centered = [
            (text.strip(), box)
            for text, box in boxes
            if text.strip() in CLOSE_GLYPHS
            and _in_popup_zone(box)
            and abs(_center(box)[0] - SCREEN_CENTER_X) <= CENTER_TOLERANCE
            and not _is_page_owned_glyph(box, boxes)
        ]
        return (centered[0][0], _center(centered[0][1])) if centered else None
    for label in DISMISS_LABELS:
        for text, box in boxes:
            if text.strip() == label and _in_popup_zone(box):
                return label, _center(box)
    glyphs = [
        (text.strip(), box)
        for text, box in boxes
        if text.strip() in CLOSE_GLYPHS
        and _in_popup_zone(box)
        and not _is_page_owned_glyph(box, boxes)
    ]
    if not glyphs:
        return None
    # 多个候选时取最靠近屏幕中线的（弹窗居中）。
    label, box = min(glyphs, key=lambda item: abs(_center(item[1])[0] - SCREEN_CENTER_X))
    return label, _center(box)


def may_have_blocking_popup(texts: Sequence[str]) -> bool:
    """只有文本、没有坐标时的预检；为真时再重新截图用 :func:`find_blocking_popup` 确认。"""
    return any(
        text.strip() in CLOSE_GLYPHS or text.strip() in DISMISS_LABELS for text in texts
    )


__all__ = [
    "find_blocking_popup",
    "is_planned_main_page",
    "may_have_blocking_popup",
]
