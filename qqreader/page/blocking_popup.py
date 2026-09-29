"""遮挡书架 / 奖励页的每日弹窗识别（只依赖一帧 OCR 文本框）。

2026-09-29 每日运行 ``daily_20260928_233026_1486afea`` 的两类弹窗：

* **奖励页每日签到弹窗**：当天第一次进奖励页时弹出「签到成功，获得10赠币」，
  下方有「看视频额外领」和「我知道了」。背景奖励页文案仍能被 OCR 读到，
  外部 App 任务在弹窗上空滑 40 秒后失败。关闭方式：点「我知道了」
  （不点「看视频额外领」，那会打开广告）。
* **书架居中运营弹窗**：跨零点后书架上弹出活动海报（本次是「双倍月票开启 /
  秋日豪礼开抢」），海报中部是「立即参与」，海报下方单独一个圆形 X。
  背景书架文案仍能读到，交接检查把它判成书架，后续任务在遮罩下空点 36 分钟。
  活动文案每期都变，而且同一活动也会以横幅出现在书城页，所以不按活动文案
  识别，而按版式识别：屏幕中部有单独的 X，正上方有居中的短按钮文案。

只返回 OCR 实际看到的按钮中心，不用固定坐标。
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

Box = Tuple[int, int, int, int]
OcrBox = Tuple[str, Box]
Target = Tuple[str, Tuple[int, int]]

SCREEN_CENTER_X = 360
CHECKIN_MARKERS = ("签到成功",)
CHECKIN_DISMISS_LABELS = ("我知道了", "知道了")
CLOSE_GLYPHS = frozenset(("X", "x", "×", "✕"))
#: 居中 X 的判定范围（720×1280）：水平偏离中线不超过 40；避开顶部状态栏 /
#: 标题栏和底部导航栏。广告页左上角 X、「我的」页被 OCR 成 X 的图标都不在此范围。
CENTER_TOLERANCE = 40
POPUP_CLOSE_MIN_Y = 300
POPUP_CLOSE_MAX_Y = 1150
#: 按钮文案在 X 上方 40～320 像素内（实测「立即参与」在 X 上方约 120 像素）。
CTA_MIN_GAP = 40
CTA_MAX_GAP = 320
CTA_MAX_CHARS = 8


def _center(box: Box) -> Tuple[int, int]:
    x, y, width, height = box
    return x + width // 2, y + height // 2


def _is_centered(box: Box, tolerance: int) -> bool:
    return abs(_center(box)[0] - SCREEN_CENTER_X) <= tolerance


def find_checkin_popup(boxes: Sequence[OcrBox]) -> Optional[Target]:
    """奖励页「签到成功」弹窗 → 「我知道了」按钮中心。"""
    if not any(marker in text for text, _ in boxes for marker in CHECKIN_MARKERS):
        return None
    for text, box in boxes:
        label = text.strip()
        if label in CHECKIN_DISMISS_LABELS:
            return label, _center(box)
    return None


def find_centered_popup_close(boxes: Sequence[OcrBox]) -> Optional[Target]:
    """居中运营弹窗 → 海报下方单独 X 的中心。"""
    for text, box in boxes:
        if text.strip() not in CLOSE_GLYPHS or not _is_centered(box, CENTER_TOLERANCE):
            continue
        top = box[1]
        if not POPUP_CLOSE_MIN_Y <= top <= POPUP_CLOSE_MAX_Y:
            continue
        has_cta = any(
            other is not box
            and 0 < len(label.strip()) <= CTA_MAX_CHARS
            and _is_centered(other, CENTER_TOLERANCE)
            and CTA_MIN_GAP <= top - other[1] <= CTA_MAX_GAP
            for label, other in boxes
        )
        if has_cta:
            return text.strip(), _center(box)
    return None


def may_have_blocking_popup(texts: Sequence[str]) -> bool:
    """只有文本、没有坐标时的预检；为真时再重新截图用 :func:`find_blocking_popup` 确认。"""
    return any(
        text.strip() in CLOSE_GLYPHS or any(m in text for m in CHECKIN_MARKERS)
        for text in texts
    )


def find_blocking_popup(boxes: Sequence[OcrBox]) -> Optional[Target]:
    """返回要点击的 (按钮文字, 中心点)；没有遮挡弹窗时返回 ``None``。"""
    return find_checkin_popup(boxes) or find_centered_popup_close(boxes)


__all__ = [
    "find_blocking_popup",
    "find_centered_popup_close",
    "find_checkin_popup",
    "may_have_blocking_popup",
]
