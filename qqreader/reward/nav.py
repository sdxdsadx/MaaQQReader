"""QQ 阅读奖励页统一 OCR 导航。

三个入口只依赖 :class:`qqreader.maa.client.MaaClient` 的截图、OCR、点击、
滑动和返回键能力，可由批处理脚本复用，也便于用假客户端离线回归。

验证码优先于背景奖励页文案：一旦识别到验证码，本模块立即停止点击并返回
失败，把控制权交给 CaptchaGuard，避免遮罩后仍可见的奖励页文字绕过守卫。
"""

from __future__ import annotations

import re
import time
from typing import Callable, List, Optional, Sequence, Tuple

from ..maa.client import Box, MaaClient
from ..page.blocking_popup import find_blocking_popup

OcrBox = Tuple[str, Box]
Sleep = Callable[[float], None]

_CAPTCHA_MARKERS = ("安全验证", "拖动下方滑块", "拖动滑块", "滑动验证", "完成拼图")
_REWARD_MARKERS = (
    "今日已获赠币",
    "今日还可领",
    "已连续签到",
    "每日阅读领赠币",
    "签到提醒",
    "看小视频领好礼",
    "玩游戏领赠币",
    "每看完1次",
    "获奖记录",
    "明日再来",
)
_SHELF_ENTRY_MARKERS = (
    "兑赠币",
    "签到领赠币",
    "分钟领",
    "本周阅读时长",
    # 2026-09-22 实机新版书架：顶部时长卡会显示
    # “38分钟 / 再读10分钟领20赠币”，不再出现旧版入口文案。
    "再读",
)
_INTRO_MARKERS = ("继续阅读", "开始阅读", "免费阅读", "阅读全文")
_BOOKSTORE_MARKERS = ("男生", "女生", "排行榜", "本周强推", "今日必读", "高分必读")
_BODY_CHAPTER = re.compile(r"第\s*\d+\s*章")
_CLOSE_TEXTS = frozenset(("X", "x", "×"))


def _ocr(client: MaaClient) -> List[OcrBox]:
    shot = client.screencap()
    result = client.recognize("OCR", {}, shot)
    return [(text, box) for text, box in result.text_boxes()]


def _joined(boxes: Sequence[OcrBox]) -> str:
    return " ".join(text for text, _ in boxes)


def _contains_any(text: str, markers: Sequence[str]) -> bool:
    return any(marker in text for marker in markers)


def _find(boxes: Sequence[OcrBox], markers: Sequence[str]) -> Optional[OcrBox]:
    for item in boxes:
        if _contains_any(item[0], markers):
            return item
    return None


def _shelf_reward_button(boxes: Sequence[OcrBox]) -> Optional[OcrBox]:
    """优先定位书架顶部时长卡右侧的领币按钮，排除底部悬浮领币图标。"""
    for item in boxes:
        label, (x, y, _, _) = item
        if x >= 420 and y < 300 and re.fullmatch(r"领\s*\d+\s*赠币|签到领赠币", label.strip()):
            return item
    return None


def _tap(client: MaaClient, item: OcrBox) -> bool:
    _, (x, y, width, height) = item
    return client.click(x + width // 2, y + height // 2)


def _sleep(delay: float, sleep: Sleep) -> None:
    if delay > 0:
        sleep(delay)


def _tap_blocking_popup(client: MaaClient, boxes: Sequence[OcrBox]) -> bool:
    """书架运营海报点 X、奖励页签到弹窗点「我知道了」；没有弹窗返回 False。"""
    popup = find_blocking_popup(boxes)
    if popup is None:
        return False
    _, (x, y) = popup
    client.click(x, y)
    return True


def dismiss_blocking_popup(client: MaaClient) -> Optional[Tuple[str, Tuple[int, int]]]:
    """重新截图；有每日弹窗就点关闭并返回 (按钮, 坐标)，验证码或无弹窗返回 None。

    只点一次，不在这里确认结果：调用方下一步会重新观测页面。
    """
    boxes = _ocr(client)
    if _contains_any(_joined(boxes), _CAPTCHA_MARKERS):
        return None
    popup = find_blocking_popup(boxes)
    if popup is None:
        return None
    client.click(*popup[1])
    return popup


def goto_reward_page(
    client: MaaClient,
    *,
    max_steps: int = 12,
    settle_seconds: float = 1.5,
    sleep: Sleep = time.sleep,
) -> bool:
    """从常见落地页导航到奖励页，成功返回 ``True``。

    分支顺序为：验证码阻塞 → 退出弹窗 → 每日弹窗 → 开屏跳过 → 简介继续阅读 →
    奖励页确认 → 书架奖励入口 → 书城切书架 → 正文页返回。未知页不盲返。所有动作
    后都重新截图确认，达到 ``max_steps`` 仍未确认奖励页则返回 ``False``。
    """
    for _ in range(max_steps):
        boxes = _ocr(client)
        text = _joined(boxes)
        if _contains_any(text, _CAPTCHA_MARKERS):
            return False

        # 广告退出确认框会透出背景奖励页，必须先处理遮罩。
        give_up = _find(boxes, ("放弃奖励", "坚持退出"))
        if give_up is not None:
            _tap(client, give_up)
            _sleep(settle_seconds, sleep)
            continue
        # 每日弹窗透出背景奖励页 / 书架文案，必须先关掉再确认页面。
        if _tap_blocking_popup(client, boxes):
            _sleep(settle_seconds, sleep)
            continue
        close = next(
            (item for item in boxes if item[0].strip() in _CLOSE_TEXTS and item[1][1] < 400),
            None,
        )
        if close is not None:
            _tap(client, close)
            _sleep(settle_seconds, sleep)
            continue

        skip = _find(boxes, ("跳过",))
        if skip is not None:
            _tap(client, skip)
            _sleep(settle_seconds, sleep)
            continue
        intro = _find(boxes, _INTRO_MARKERS)
        if intro is not None:
            _tap(client, intro)
            _sleep(settle_seconds, sleep)
            continue
        if _contains_any(text, _REWARD_MARKERS):
            return True

        # 书架顶部卡片同时包含说明文案和蓝色“签到领赠币”按钮；说明文案
        # 本身在部分版本不可点击。优先点击按钮，找不到时才退回卡片文案。
        entry = _shelf_reward_button(boxes) or _find(boxes, _SHELF_ENTRY_MARKERS)
        if entry is not None:
            _tap(client, entry)
            _sleep(settle_seconds, sleep)
            continue

        bookstore_hits = sum(marker in text for marker in _BOOKSTORE_MARKERS)
        if bookstore_hits >= 2:
            client.click(70, 1250)
            _sleep(settle_seconds, sleep)
            continue

        # 正文（第 N 章）显式走 BACK；无法确认的页面停止导航，交给
        # 上层页面状态确认。否则刚进入奖励页但 OCR 文案变化时会被关掉。
        if _BODY_CHAPTER.search(text):
            client.click_key(4)
            _sleep(settle_seconds, sleep)
            continue
        return False
    return False


def find_watch_entry(
    client: MaaClient,
    *,
    max_scrolls: int = 8,
    settle_seconds: float = 1.0,
    sleep: Sleep = time.sleep,
) -> Optional[OcrBox]:
    """在奖励页逐屏查找「立即观看」；位于底部时先回到中段。"""
    toward_top: Optional[bool] = None
    for scroll_no in range(max_scrolls + 1):
        boxes = _ocr(client)
        text = _joined(boxes)
        if _contains_any(text, _CAPTCHA_MARKERS):
            return None
        if _tap_blocking_popup(client, boxes):
            # 签到弹窗盖在奖励页上时滑动无效：本轮只关弹窗、不滑动；
            # 仍占用一轮循环，弹窗关不掉时不会无限点击。
            _sleep(settle_seconds, sleep)
            continue
        watch = _find(boxes, ("立即观看",))
        if watch is not None:
            return watch
        if scroll_no < max_scrolls:
            if toward_top is None:
                toward_top = _contains_any(
                    text, ("抽奖回馈", "回到顶部", "连续签到180天")
                )
            if toward_top:
                # 手指向下滑，页面内容回到更靠上的视频任务区域。
                client.swipe(360, 400, 360, 1100, 500)
            else:
                client.swipe(360, 1150, 360, 400, 500)
            _sleep(settle_seconds, sleep)
    return None


def back_to_reward(
    client: MaaClient,
    *,
    max_steps: int = 8,
    settle_seconds: float = 1.5,
    sleep: Sleep = time.sleep,
) -> bool:
    """从广告逐层退出到奖励页；优先放弃按钮、顶部 X，最后才 BACK。"""
    for _ in range(max_steps):
        boxes = _ocr(client)
        text = _joined(boxes)
        if _contains_any(text, _CAPTCHA_MARKERS):
            return False

        give_up = _find(boxes, ("放弃奖励", "坚持退出"))
        if give_up is not None:
            _tap(client, give_up)
            _sleep(settle_seconds, sleep)
            continue
        # 每日弹窗透出背景奖励页 / 书架文案，必须先关掉再确认页面。
        if _tap_blocking_popup(client, boxes):
            _sleep(settle_seconds, sleep)
            continue
        close = next(
            (item for item in boxes if item[0].strip() in _CLOSE_TEXTS and item[1][1] < 400),
            None,
        )
        if close is not None:
            _tap(client, close)
            _sleep(settle_seconds, sleep)
            continue
        if _contains_any(text, _REWARD_MARKERS):
            return True

        client.click_key(4)
        _sleep(settle_seconds, sleep)
    return False


__all__ = ["back_to_reward", "dismiss_blocking_popup", "find_watch_entry", "goto_reward_page"]
