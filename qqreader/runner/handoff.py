"""串行任务之间的交接检查（QQR-53）。

上一项任务结束（无论成功还是失败）后，屏幕可能仍停在广告、挽留弹窗、
正文页或验证码上。下一项任务如果直接启动，就会在错误页面上开跑
（2026-09-27 ``daily_20260927_114947_a58b6564``：等级广告停在「继续观看 /
放弃奖励」弹窗，听书随即从广告页启动并失败）。

本模块在两项任务之间做一次「识别 → 动作 → 重新截图确认」的交接：

* 任何一帧出现验证码 → 立即返回 ``CAPTCHA``，不点击、不返回、不重启；
* 已确认在书架（所有每日任务共同的公共起点）→ ``READY``；
* 否则按页面类型处理：确认框点「取消」、广告挽留弹窗点「放弃奖励」、
  每日运营 / 签到弹窗点 X 或「我知道了」、
  书城切到「书架」tab、开屏点「跳过」，其余页面按返回键；返回耗尽后
  重启一次 App；每个动作之后都重新截图确认；
* 仍无法确认 → ``UNSAFE``，由调度方跳过下一项任务并保留原因。

只依赖 :class:`~qqreader.maa.client.MaaClient` 的截图、OCR、点击、返回键和
App 启停能力，便于用真实 OCR 帧离线回归。
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

from ..maa.client import Box, MaaClient
from ..page.blocking_popup import find_blocking_popup

OcrBox = Tuple[str, Box]
Sleep = Callable[[float], None]

KEYCODE_BACK = 4

CAPTCHA_MARKERS = ("安全验证", "拖动下方滑块", "拖动滑块", "滑动验证", "完成拼图")
#: 书架页独有的文本；底部「书架」tab 在所有主页 tab 上都有，不能单独作依据。
SHELF_MARKERS = ("本周未开始阅读", "时长兑赠币", "我的笔记", "签到领赠币")
#: 书籍进度行「84章/372章」；不能用子串「章/」，它会误中书城横幅「勋章/装扮限时返场」（QQR-55）。
SHELF_PROGRESS_PATTERN = re.compile(r"\d+章/\d+章")
BOOKSTORE_MARKERS = ("男生", "女生", "排行榜", "本周强推", "今日必读", "高分必读")
EXIT_DIALOG_MARKERS = ("确定退出QQ阅读", "退出QQ阅读？")
UPGRADE_DIALOG_MARKERS = ("已下载新版本", "是否安装", "安装新版本")
#: 广告挽留弹窗（2026-09-27 实测文案：「观看视频30秒，才能获得奖励」「继续观看」「放弃奖励」）。
RETENTION_MARKERS = ("放弃奖励", "坚持退出")
BOTTOM_NAV_MIN_Y = 1150
#: 同一页面类型上的定向动作（点取消 / 放弃奖励 / 书架 tab / 跳过）连续无效的上限；
#: 超过后改走返回 / 重启，避免在同一处反复点击。
MAX_SAME_TARGETED_ACTIONS = 2


class HandoffVerdict(str, Enum):
    READY = "READY"
    CAPTCHA = "CAPTCHA"
    UNSAFE = "UNSAFE"


class FrameKind(str, Enum):
    CAPTCHA = "CAPTCHA"
    EXIT_DIALOG = "EXIT_DIALOG"
    UPGRADE_DIALOG = "UPGRADE_DIALOG"
    AD_RETENTION = "AD_RETENTION"
    BLOCKING_POPUP = "BLOCKING_POPUP"
    SHELF = "SHELF"
    BOOKSTORE = "BOOKSTORE"
    SPLASH = "SPLASH"
    NO_TEXT = "NO_TEXT"
    OTHER = "OTHER"


@dataclass(frozen=True)
class HandoffResult:
    verdict: HandoffVerdict
    reason: str
    frame: FrameKind
    actions: Tuple[str, ...] = ()
    last_ocr: Tuple[str, ...] = ()
    evidence: Optional[Path] = None

    @property
    def ready(self) -> bool:
        return self.verdict is HandoffVerdict.READY


def _joined(boxes: Sequence[OcrBox]) -> str:
    return " ".join(text.replace(" ", "") for text, _ in boxes)


def _find_exact(boxes: Sequence[OcrBox], labels: Sequence[str]) -> Optional[OcrBox]:
    for item in boxes:
        if item[0].strip() in labels:
            return item
    return None


def _find_containing(boxes: Sequence[OcrBox], markers: Sequence[str]) -> Optional[OcrBox]:
    for item in boxes:
        if any(marker in item[0] for marker in markers):
            return item
    return None


def bookstore_hits(text: str) -> int:
    return sum(marker in text for marker in BOOKSTORE_MARKERS)


def is_shelf_text(text: str) -> bool:
    """书架判定：必须有书架独有文本，且不能同时像书城页。"""
    if bookstore_hits(text) >= 2:
        return False
    if any(marker in text for marker in SHELF_MARKERS):
        return True
    return "再读" in text and SHELF_PROGRESS_PATTERN.search(text) is not None


def has_shelf_label(boxes: Sequence[OcrBox]) -> bool:
    """书架页顶部标题或底部 tab 上的「书架」二字（奖励页没有）。"""
    return any(
        text.strip() == "书架" and (box[1] < 120 or box[1] >= BOTTOM_NAV_MIN_Y)
        for text, box in boxes
    )


def classify_frame(boxes: Sequence[OcrBox]) -> FrameKind:
    """按优先级给一帧 OCR 分类：验证码 > 遮罩弹窗 > 书架 > 书城 > 其他。"""
    if not boxes:
        return FrameKind.NO_TEXT
    text = _joined(boxes)
    if any(marker in text for marker in CAPTCHA_MARKERS):
        return FrameKind.CAPTCHA
    # 确认框会透出背景页（书架/书城），必须先于页面判定。
    if any(marker in text for marker in EXIT_DIALOG_MARKERS) and _find_exact(boxes, ("取消",)):
        return FrameKind.EXIT_DIALOG
    if any(marker in text for marker in UPGRADE_DIALOG_MARKERS) and _find_exact(boxes, ("取消",)):
        return FrameKind.UPGRADE_DIALOG
    if _find_exact(boxes, RETENTION_MARKERS) is not None:
        return FrameKind.AD_RETENTION
    # 书架上的运营海报 / 奖励页签到弹窗同样透出背景文案（2026-09-28 书架弹窗
    # 被判成书架，后续任务在遮罩下空点 36 分钟）。
    if find_blocking_popup(boxes) is not None:
        return FrameKind.BLOCKING_POPUP
    if is_shelf_text(text) and has_shelf_label(boxes):
        return FrameKind.SHELF
    # 只有底部导航里真的看得到「书架」tab 才算可切换的书城主页；排行榜等二级页
    # 也有「男生 / 女生」，但没有底部 tab，按其他页面返回（2026-09-27 实机 S4a）。
    if bookstore_hits(text) >= 2 and _shelf_tab(boxes) is not None:
        return FrameKind.BOOKSTORE
    if _find_containing(boxes, ("跳过",)) is not None:
        return FrameKind.SPLASH
    return FrameKind.OTHER


def _center(box: Box) -> Tuple[int, int]:
    x, y, width, height = box
    return x + width // 2, y + height // 2


def _shelf_tab(boxes: Sequence[OcrBox]) -> Optional[Tuple[int, int]]:
    """底部导航里 OCR 实际看到的「书架」tab；看不到就不点（不用固定坐标兜底）。"""
    for text, box in boxes:
        if text.strip() == "书架" and box[1] >= BOTTOM_NAV_MIN_Y:
            return _center(box)
    return None


def _targeted_action(kind: FrameKind, boxes: Sequence[OcrBox]) -> Optional[Tuple[str, Tuple[int, int]]]:
    """按页面类型给出要点的 OCR 框中心；只点 OCR 实际看到的文字，不用固定坐标。"""
    if kind in (FrameKind.EXIT_DIALOG, FrameKind.UPGRADE_DIALOG):
        item = _find_exact(boxes, ("取消",))
    elif kind is FrameKind.AD_RETENTION:
        item = _find_exact(boxes, RETENTION_MARKERS)
    elif kind is FrameKind.BLOCKING_POPUP:
        return find_blocking_popup(boxes)
    elif kind is FrameKind.BOOKSTORE:
        point = _shelf_tab(boxes)
        return ("书架tab", point) if point is not None else None
    elif kind is FrameKind.SPLASH:
        item = _find_containing(boxes, ("跳过",))
    else:
        return None
    if item is None:
        return None
    return item[0].strip(), _center(item[1])


class _Screen:
    def __init__(self, client: MaaClient) -> None:
        self._client = client
        self.last_shot = None

    def ocr(self) -> List[OcrBox]:
        shot = self._client.screencap()
        self.last_shot = shot
        result = self._client.recognize("OCR", {}, shot)
        return [(text, box) for text, box in result.text_boxes()]


def check_handoff(
    client: MaaClient,
    *,
    package: str,
    max_rounds: int = 16,
    max_backs: int = 4,
    allow_restart: bool = True,
    settle_seconds: float = 2.0,
    restart_wait_seconds: float = 10.0,
    evidence_dir: Optional[Path] = None,
    sleep: Sleep = time.sleep,
) -> HandoffResult:
    """把设备带回书架并确认；验证码出现时立即停手。"""
    screen = _Screen(client)
    actions: List[str] = []
    backs = 0
    restarted = False
    boxes: List[OcrBox] = []
    kind = FrameKind.NO_TEXT
    last_targeted: Optional[FrameKind] = None
    same_kind_repeats = 0

    def finish(verdict: HandoffVerdict, reason: str) -> HandoffResult:
        evidence = _save_evidence(screen.last_shot, evidence_dir, verdict)
        return HandoffResult(
            verdict=verdict,
            reason=reason,
            frame=kind,
            actions=tuple(actions),
            last_ocr=tuple(text for text, _ in boxes),
            evidence=evidence,
        )

    def act(description: str, delay: float = settle_seconds) -> None:
        actions.append(f"{description} @{kind.value}")
        if delay > 0:
            sleep(delay)

    for _ in range(max_rounds):
        boxes = screen.ocr()
        kind = classify_frame(boxes)
        if kind is FrameKind.CAPTCHA:
            return finish(HandoffVerdict.CAPTCHA, "交接检查发现验证码，停止后续任务，等待人工")
        if kind is FrameKind.SHELF:
            return finish(HandoffVerdict.READY, "已确认在书架")
        target = _targeted_action(kind, boxes)
        if target is not None:
            same_kind_repeats = same_kind_repeats + 1 if kind is last_targeted else 1
            last_targeted = kind
            if same_kind_repeats <= MAX_SAME_TARGETED_ACTIONS:
                label, point = target
                client.click(*point)
                act(f"TAP {label}{point}")
                continue
            # 同一处连续点了仍在原页面：不再重复点击，改走返回 / 重启。
        else:
            last_targeted = None
        # 广告页、正文页（禁止截图时 OCR 为空）、奖励页等：逐次返回并重新确认。
        if backs < max_backs:
            backs += 1
            client.click_key(KEYCODE_BACK)
            act(f"BACK {backs}/{max_backs}")
            continue
        if allow_restart and not restarted:
            restarted = True
            backs = 0
            last_targeted = None
            client.stop_app(package)
            client.start_app(package)
            act("RESTART_APP", restart_wait_seconds)
            continue
        break
    return finish(
        HandoffVerdict.UNSAFE,
        f"返回{'并重启 App ' if restarted else ''}后仍未确认书架，最后页面类型 {kind.value}",
    )


def _save_evidence(shot, evidence_dir: Optional[Path], verdict: HandoffVerdict) -> Optional[Path]:
    if shot is None or evidence_dir is None:
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target = Path(evidence_dir) / f"handoff_{stamp}_{verdict.value}.png"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        return Path(shot.save(target))
    except Exception:  # noqa: BLE001 - 证据保存失败不改变交接结论
        return None


__all__ = [
    "FrameKind",
    "HandoffResult",
    "HandoffVerdict",
    "check_handoff",
    "classify_frame",
    "has_shelf_label",
    "is_shelf_text",
]
