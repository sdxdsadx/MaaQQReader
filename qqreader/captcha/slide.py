"""滑动验证码求解器（OpenCV 轨道/滑块/缺口检测 + MAA 滑动）。

检测算法移植自旧工程 ``tools/slide_captcha_solver.py`` 中已被验证有效的
蓝色滑块 + 灰色轨道 + 缺口检测；求解动作改走新的 ``DeviceController.swipe``，
不再依赖旧仓库脚本。

设计约束（AGENTS.md §3.8）：

* 只负责「提交一次滑动」；是否真的通过由 ``VerifyingCaptchaGuard`` 复核；
* 检测不到轨道/滑块/缺口时返回 ``solved=False``，绝不盲滑；
* 缺少 OpenCV/numpy 时返回明确原因，由 guard 进入人工等待。
"""

from __future__ import annotations

import random
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from .guard import SolveResult

if TYPE_CHECKING:  # pragma: no cover
    from ..runtime.context import TaskContext
    from ..runtime.device import DeviceController
    from ..runtime.observer import PageObserver

try:  # pragma: no cover - 环境相关
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore
    np = None  # type: ignore


@dataclass(frozen=True)
class SlideDetection:
    found: bool
    error: str = ""
    track: Tuple[int, int, int, int] = (0, 0, 0, 0)
    slider: Tuple[int, int, int, int] = (0, 0, 0, 0)
    slider_center: Tuple[int, int] = (0, 0)
    target: Tuple[int, int] = (0, 0)
    distance: int = 0


def _longest_gray_run(gray: Any, yy: int) -> Tuple[int, int]:
    row = gray[yy, :]
    mask = (row >= 180) & (row <= 220)
    max_run = 0
    run = 0
    start = 0
    best_start = 0
    for x, value in enumerate(mask):
        if value:
            if run == 0:
                start = x
            run += 1
            if run > max_run:
                max_run = run
                best_start = start
        else:
            run = 0
    return max_run, best_start


def _find_track_and_slider(image: Any):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]

    blue = cv2.inRange(image, (180, 50, 0), (255, 220, 180))
    blue = cv2.morphologyEx(blue, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    slider = None
    slider_area = 0.0
    for contour in contours:
        if contour is None or len(contour) == 0:
            continue
        x, y, cw, ch = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)
        if area < 500:
            continue
        if not (60 <= cw <= 180 and 35 <= ch <= 100):
            continue
        if slider is None or area > slider_area:
            slider = (x, y, cw, ch)
            slider_area = area

    if slider is not None:
        slider_cy = slider[1] + slider[3] / 2
        y0 = max(0, int(slider_cy - 60))
        y1 = min(h, int(slider_cy + 60))
        rows = []
        best_row = None
        for yy in range(y0, y1):
            max_run, best_start = _longest_gray_run(gray, yy)
            if max_run > w * 0.40:
                rows.append(yy)
                if best_row is None or max_run > best_row[0]:
                    best_row = (max_run, best_start, yy)
        if rows and best_row is not None:
            y_top = min(rows)
            y_bot = max(rows)
            mid_y = (y_top + y_bot) // 2
            mid = gray[mid_y, :]
            mask = (mid >= 180) & (mid <= 220)
            xs = np.where(mask)[0]
            if len(xs) > 0:
                track = (
                    int(xs.min()),
                    y_top,
                    int(xs.max()) - int(xs.min()) + 1,
                    y_bot - y_top + 1,
                )
                return track, slider
        return None, slider

    # 没有蓝色滑块时，先找宽灰色轨道，再在轨道附近找滑块。
    search_y0 = int(h * 0.40)
    search_y1 = h - 60
    best_line = None
    for yy in range(search_y0, search_y1):
        max_run, best_start = _longest_gray_run(gray, yy)
        if max_run > w * 0.40:
            if best_line is None or max_run > best_line[0]:
                best_line = (max_run, best_start, yy)
    if best_line is None:
        return None, None

    _, _, peak_y = best_line
    rows = []
    for yy in range(max(0, peak_y - 30), min(h, peak_y + 31)):
        max_run, _ = _longest_gray_run(gray, yy)
        if max_run > w * 0.40:
            rows.append(yy)
    if not rows:
        return None, None
    y_top = min(rows)
    y_bot = max(rows)
    mid = gray[(y_top + y_bot) // 2, :]
    mask = (mid >= 180) & (mid <= 220)
    xs = np.where(mask)[0]
    if len(xs) == 0:
        return None, None
    track = (
        int(xs.min()),
        y_top,
        int(xs.max()) - int(xs.min()) + 1,
        y_bot - y_top + 1,
    )

    slider = None
    slider_area = 0.0
    track_cy = y_top + (y_bot - y_top) // 2
    for contour in contours:
        if contour is None or len(contour) == 0:
            continue
        x, y, cw, ch = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)
        if area < 500:
            continue
        if not (60 <= cw <= 180 and 35 <= ch <= 100):
            continue
        if abs((y + ch / 2) - track_cy) > 80:
            continue
        if slider is None or area > slider_area:
            slider = (x, y, cw, ch)
            slider_area = area
    return track, slider


def _find_gap_x(gray: Any, track: Tuple[int, int, int, int], slider: Tuple[int, int, int, int]) -> Optional[int]:
    x, y, cw, ch = track
    h, w = gray.shape[:2]
    x1 = max(0, x + 10)
    x2 = min(w, x + cw - 10)
    y1 = max(0, y - 300)
    y2 = max(y1 + 20, y - 35)
    if x2 - x1 < 30 or y2 - y1 < 30:
        return None

    roi = gray[y1:y2, x1:x2]
    _, th = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    for contour in contours:
        if contour is None or len(contour) == 0:
            continue
        bx, by, bw, bh = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)
        if area < 500 or area > 25000:
            continue
        if not (20 <= bw <= 150 and 20 <= bh <= 150):
            continue
        if bx <= 2 or by <= 2 or bx + bw >= roi.shape[1] - 2:
            continue
        candidates.append((float(area), bx, by, bw, bh))
    if candidates:
        candidates.sort(reverse=True)
        _, bx, by, bw, bh = candidates[0]
        gap_x = x1 + bx + bw // 2
        if slider[0] + slider[2] < gap_x:
            return int(gap_x)

    edges = cv2.Canny(roi, 50, 150)
    col_density = edges.sum(axis=0) / max(1, edges.shape[0])
    search_start = max(0, slider[0] - x1 + slider[2])
    search_end = max(search_start + 10, roi.shape[1] - 60)
    if search_start >= search_end:
        return None
    search = col_density[search_start:search_end]
    if search.size < 10:
        return None
    kernel = np.ones(7, dtype=float) / 7
    smoothed = np.convolve(search, kernel, mode="same")
    idx = int(np.argmax(smoothed))
    if smoothed[idx] < 1.0:
        return None
    return int(x1 + search_start + idx)


def detect_slide(image_bytes: bytes) -> SlideDetection:
    """从 PNG/JPEG 字节检测轨道、滑块与缺口；失败时 found=False。"""
    if cv2 is None or np is None:
        return SlideDetection(False, "未安装 opencv-python / numpy")
    try:
        image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    except Exception as exc:  # pragma: no cover - 解码异常
        return SlideDetection(False, f"截图解码失败: {exc}")
    if image is None or image.size == 0:
        return SlideDetection(False, "截图为空或无法解码")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    track, slider = _find_track_and_slider(image)
    if track is None or slider is None:
        return SlideDetection(False, "未检测到滑块轨道/滑块按钮")
    gap_x = _find_gap_x(gray, track, slider)
    if gap_x is None:
        return SlideDetection(
            False,
            "未检测到滑块缺口位置",
            track=tuple(int(v) for v in track),  # type: ignore[arg-type]
            slider=tuple(int(v) for v in slider),  # type: ignore[arg-type]
        )
    slider_cx = slider[0] + slider[2] // 2
    slider_cy = slider[1] + slider[3] // 2
    distance = gap_x - slider_cx
    if distance <= 0 or distance > track[2] * 1.5:
        return SlideDetection(
            False,
            f"滑块距离异常：{distance}",
            track=tuple(int(v) for v in track),  # type: ignore[arg-type]
            slider=tuple(int(v) for v in slider),  # type: ignore[arg-type]
        )
    return SlideDetection(
        True,
        "",
        track=tuple(int(v) for v in track),  # type: ignore[arg-type]
        slider=tuple(int(v) for v in slider),  # type: ignore[arg-type]
        slider_center=(int(slider_cx), int(slider_cy)),
        target=(int(slider_cx + distance), int(slider_cy)),
        distance=int(distance),
    )


class SlideCaptchaSolver:
    """基于 ``PageObserver`` 截图 + ``DeviceController.swipe`` 的滑块求解器。"""

    def __init__(
        self,
        *,
        observer: "PageObserver",
        device: "DeviceController",
        swipe_duration_ms: int = 600,
        puzzle_scale: float = 2.14,
    ) -> None:
        self._observer = observer
        self._device = device
        self._swipe_duration_ms = swipe_duration_ms
        # QQ阅读验证码：滑块轨道可视宽 414px，拼图区显示宽 193px，
        # 拼图头位移/按钮位移 ≈ 2.14（r2/r3 截图差分实测 441/206=2.141）。
        self._puzzle_scale = puzzle_scale

    def _capture(self, context: "TaskContext") -> Optional[bytes]:
        observation = self._observer.observe(context)
        context.update_data(captcha_last_observation=observation.summary())
        shot = getattr(self._observer, "last_screenshot", None)
        data = getattr(shot, "data", None)
        if data:
            return bytes(data)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "captcha.png"
            saved = self._observer.save_last_screenshot(path)
            if saved is not None and Path(saved).is_file():
                return Path(saved).read_bytes()
        return None

    def _humanize_swipe(self, sx: int, sy: int, tx: int, ty: int, distance: int) -> None:
        """拟人滑动：分段轨迹 + 过冲回正 + 轻微抖动 + 随机时长。

        r2 实测：匀速直线 600ms 滑动两次都被行为检测拒绝（滑了 206px 仍判
        失败）。改为先快后慢的分段 swipe：主段快速接近（含 3~8px 随机过冲），
        停顿一拍后微调回正；纵向抖动 ±2px 模拟手指不稳。
        """
        base = max(350, min(900, int(distance * 2.2)))
        duration = base + random.randint(-60, 120)
        overshoot = random.randint(3, 8)
        jx = random.randint(-2, 2)
        jy = random.randint(-2, 2)
        # 主段：快速滑到目标 + 过冲
        self._device.swipe(sx, sy, tx + overshoot, ty + jy, duration)
        time.sleep(random.uniform(0.08, 0.18))
        # 回正段：慢速小幅拉回，像人手对齐拼图
        self._device.swipe(
            tx + overshoot, ty + jy, tx + random.randint(-1, 1), ty, random.randint(180, 320)
        )

    def solve(self, context: "TaskContext") -> SolveResult:
        data = self._capture(context)
        if not data:
            return SolveResult(False, "无法获取验证码截图")
        detection = detect_slide(data)
        if not detection.found:
            return SolveResult(
                False,
                detection.error or "未检测到可滑动的验证码",
                data={
                    "track": detection.track,
                    "slider": detection.slider,
                },
            )
        sx, sy = detection.slider_center
        tx, ty = detection.target
        raw_distance = detection.distance

        # issue #16 终修：轨道→拼图区比例尺换算。
        # 实测（r2/r3 截图差分）：按钮滑 206px，拼图头实际移动 441px——
        # 「屏幕坐标差」≠「拼图位移」。按钮位移永远 1:1（蓝色按钮就在轨道上），
        # 拼图头才被缩放，而检测器只能测到按钮 → 探针标定测不出真实 scale
        # （r4 实证 scale 恒测得 1.00）。改用实测先验 scale≈2.14
        # （轨道可视宽 414 / 拼图区显示宽 193），修正距离 = raw / scale。
        scale = self._puzzle_scale
        corrected = int(round(raw_distance / scale))
        self._humanize_swipe(sx, sy, sx + corrected, sy, corrected)
        return SolveResult(
            True,
            f"已滑动 {corrected}px（比例尺 {scale:.2f}，原始 {raw_distance}px）",
            data={
                "slider_center": detection.slider_center,
                "target": detection.target,
                "distance": raw_distance,
                "corrected": corrected,
                "scale": round(scale, 3),
            },
        )
