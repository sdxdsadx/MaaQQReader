"""滑动验证码求解器（OpenCV 轨道/滑块/缺口检测 + MAA 滑动）。

检测算法移植自旧工程 ``tools/slide_captcha_solver.py`` 中已被验证有效的
蓝色滑块 + 灰色轨道 + 缺口检测；求解动作改走新的 ``DeviceController.swipe``，
不再依赖旧仓库脚本。

设计约束（AGENTS.md §3.8）：

* 求解循环（2026-09-12 活体实证）：单次滑动被拒后拼图会**重新随机化**
  （实测 dist 244→340），因此失败后必须在新鲜帧上重检测再滑，禁止在
  旧坐标上盲补；每轮滑动后等待 ``settle_seconds`` 再复查；
* OCR 复查到验证码文案（安全验证/拖动滑块等）仍在时，返回 ``solved=False``，
  绝不谎报成功；OCR 不可用（无文本帧）时提交一次滑动并交由 guard 复核；
* 检测不到轨道/滑块/缺口时等待后复检一次，仍失败返回 ``solved=False``，
  绝不盲滑；缺少 OpenCV/numpy 时返回明确原因，由 guard 进入人工等待。
"""

from __future__ import annotations

import random
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from .guard import SolveResult
from ..runtime.clock import RealClock

if TYPE_CHECKING:  # pragma: no cover
    from ..runtime.clock import Clock
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

    # OCR 复查判定「验证码仍在」的文案特征（与 captcha_condition 特征键同源）。
    CAPTCHA_TEXT_KEYS = ("安全验证", "拖动下方滑块", "拖动滑块", "滑动验证", "完成拼图")

    def __init__(
        self,
        *,
        observer: "PageObserver",
        device: "DeviceController",
        swipe_duration_ms: int = 600,
        puzzle_scale: float = 2.14,
        head_bias: int = 29,
        max_rounds: int = 6,
        settle_seconds: float = 2.5,
        redetect_wait_seconds: float = 2.0,
        clock: Optional["Clock"] = None,
    ) -> None:
        self._observer = observer
        self._device = device
        self._swipe_duration_ms = swipe_duration_ms
        # QQ阅读验证码：滑块轨道可视宽 414px，拼图区显示宽 193px，
        # 拼图头位移/按钮位移 ≈ 2.14（r2/r3 截图差分实测 441/206=2.141）。
        self._puzzle_scale = puzzle_scale
        # 拼图头起点相对按钮中心的屏幕偏置（r2 实测 197-168=29px）。
        self._head_bias = head_bias
        # 求解循环节奏（2026-09-12 活体实证固化）：
        # 单次滑动被拒后拼图重新随机化，必须「重检测→再滑」迭代而非盲补。
        if max_rounds < 1:
            raise ValueError("max_rounds 必须 >= 1")
        self._max_rounds = max_rounds
        self._settle_seconds = settle_seconds      # 滑动后等待校验动画
        self._redetect_wait_seconds = redetect_wait_seconds  # 检测失败后的过渡等待
        self._clock: "Clock" = clock if clock is not None else RealClock()

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
        """拟人滑动：sendevent 原始触摸流（变速 + 抖动 + 过冲回调）。

        活体实验（runtime/logs live_sendevent，2026-09-11）实证：MAA/adb
        input swipe 的匀速直线轨迹被行为指纹识别拒绝（回弹）；sendevent
        注入「ease-out 变速 + y 抖动 + 过冲微回调」原始事件流一次通过。
        dx = tx - sx 为目标位移。
        """
        dx = tx - sx
        dy = ty - sy
        track = self._human_track(dx)
        self._sendevent_track(sx, sy, track, dy)

    def _adb_shell(self, config: Any, script: str) -> None:
        import subprocess

        subprocess.run(
            [config.machine.adb_path, "-s", config.machine.adb_address,
             "shell", script],
            capture_output=True, timeout=20,
        )

    def _human_track(self, dx: int) -> list:
        """ease-out 变速轨迹: [(x_offset, dt_ms), ...]，含过冲与回调。"""
        pts = []
        over = random.randint(4, 9) * (1 if dx > 0 else -1)
        n = max(12, min(40, abs(dx) // 6))
        for i in range(1, n + 1):
            f = i / n
            ease = 1 - (1 - f) ** 2
            dt = random.randint(14, 34)
            pts.append((int(dx * ease) - int(dx * (1 - (i - 1) / n) ** 2) * 0, dt))
        # 上面的 ease 序列直接用绝对位置更稳，重新生成:
        pts = []
        prev = 0
        for i in range(1, n + 1):
            f = i / n
            ease = 1 - (1 - f) ** 2
            x = int(dx * ease)
            pts.append((x - prev, random.randint(14, 34)))
            prev = x
        pts.append((over, random.randint(20, 40)))
        pts.append((-over, random.randint(25, 50)))
        return pts

    def _sendevent_track(self, sx: int, sy: int, track: list, dy: int) -> None:
        from ..config import load_config  # 局部导入避免循环

        config = load_config("configs/qqreader.local.json")
        adb = config.machine.adb_path
        dev = config.machine.adb_address

        import subprocess

        r = subprocess.run(
            [adb, "-s", dev, "shell", "getevent", "-pl"],
            capture_output=True, text=True, timeout=20,
        )
        tdev = None
        cur = None
        for line in r.stdout.splitlines():
            m = re.search(r"add device \d+: (/dev/input/event\d+)", line)
            if m:
                cur = m.group(1)
            if cur and "ABS_MT_POSITION_X" in line:
                tdev = cur
                break
        if not tdev:
            # 无触屏设备：退化为设备 swipe（可能被行为检测拒绝）
            self._device.swipe(sx, sy, sx + sum(d for d, _ in track), sy,
                               self._swipe_duration_ms)
            return

        def send(events):
            script = "".join(f"sendevent {tdev} {t} {c} {v}; " for t, c, v in events)
            subprocess.run([adb, "-s", dev, "shell", script],
                           capture_output=True, timeout=20)

        x = sx
        y = sy
        send([(3, 57, 0), (3, 53, x), (3, 54, y), (1, 330, 1), (0, 0, 0)])
        time.sleep(0.05)
        for ddx, dt in track:
            x += ddx
            y = sy + random.randint(-2, 2)
            send([(3, 53, x), (3, 54, y), (0, 0, 0)])
            time.sleep(dt / 1000.0)
        time.sleep(random.uniform(0.08, 0.2))
        send([(3, 57, -1), (1, 330, 0), (0, 0, 0)])

    def _observe_texts(self, context: "TaskContext") -> Tuple[str, ...]:
        """重新观测当前帧并返回 OCR 文案（observe 已更新 context.observation）。"""
        observation = self._observer.observe(context)
        context.update_observation(observation, getattr(context, "decision", None))
        return tuple(observation.ocr_texts)

    def solve(self, context: "TaskContext") -> SolveResult:
        """滑块求解循环（2026-09-12 活体迭代实证）。

        循环节奏（最多 ``max_rounds`` 轮）：

        1. 新鲜截图 → ``detect_slide``；检测不到时等待 ``redetect_wait_seconds``
           后复检一次（可能是弹窗过渡态），仍检测不到才放弃（绝不盲滑）；
        2. 用新鲜帧的 raw 距离发 sendevent 拟人轨迹（ease-out 变速 + y 抖动 +
           过冲回调；单段 swipe 的匀速直线会被行为指纹识别拒绝→回弹）；
        3. 等待 ``settle_seconds`` 让校验动画走完，再取新鲜帧判定；
        4. 判定：OCR 出现验证码文案（安全验证/拖动滑块/完成拼图等）→ 本轮
           失败。关键教训（活体实证）：滑动被拒后拼图会**重新随机化**
           （dist 244→340），必须用新鲜帧重检测再滑，禁止在旧坐标上盲补；
        5. OCR 无验证码文案：若帧上完全没有文本（合成图/OCR 不可用），
           按契约「提交成功、guard 复核」返回 solved=True；否则确认验证码
           已消失，直接返回 solved=True。

        注意：OCR 判「仍在」时进入下一轮重检测再滑（受 ``max_rounds`` 限制），
        轮次耗尽后返回 ``solved=False`` → guard 进入人工等待。
        """
        details = []
        redetect_used = False
        for round_no in range(1, self._max_rounds + 1):
            data = self._capture(context)
            if not data:
                return SolveResult(False, "无法获取验证码截图", data={"rounds": details})
            detection = detect_slide(data)
            if not detection.found:
                if redetect_used:
                    return SolveResult(
                        False,
                        detection.error or "未检测到可滑动的验证码",
                        data={"track": detection.track, "slider": detection.slider,
                              "rounds": details},
                    )
                redetect_used = True
                self._clock.sleep(self._redetect_wait_seconds, context.token)
                details.append(
                    f"第 {round_no} 轮未检测到轨道（{detection.error}），等待 "
                    f"{self._redetect_wait_seconds:.1f}s 复检"
                )
                continue

            redetect_used = False
            sx, sy = detection.slider_center
            gap_x = detection.slider_center[0] + detection.distance

            # issue #16 终修（活体实验定案 2026-09-11）+ 迭代循环（2026-09-12）：
            #   1. 拼图头与按钮 1:1 同步移动（sendevent 连拍实证）
            #   2. 单段 swipe 的匀速直线轨迹被行为指纹识别 → 校验拒绝 → 回弹
            #   3. sendevent 注入「ease-out 变速 + y 抖动 + 过冲回调」原始
            #      触摸事件流一次通过（live_sendevent.py 实证 ✅）
            #   4. 被拒后拼图重新随机化 → 必须每轮在新鲜帧上重检测再滑
            self._humanize_swipe(
                sx, sy, sx + detection.distance, sy, detection.distance
            )
            self._clock.sleep(self._settle_seconds, context.token)
            details.append(
                f"第 {round_no} 轮已滑动 {detection.distance}px"
                f"（起点({sx},{sy})→缺口x={gap_x}）"
            )

            # 复查: 重新观测, 看 OCR 文案里验证码是否仍在。
            verify_texts = self._observe_texts(context)
            still_on = any(key in text for text in verify_texts for key in self.CAPTCHA_TEXT_KEYS)
            if still_on:
                details.append("OCR 复查验证码文案仍在 → 重新检测缺口再滑")
                continue
            # OCR 复查不到验证码文案。帧上完全无文本时（合成图/OCR 不可用）
            # 无法自行确认，按契约返回提交成功、由 guard 重新观测复核；
            # 有文本但无验证码文案 = 确认消失。
            note = "OCR 复查确认验证码文案已消失" if verify_texts else "OCR 无文本（OCR 不可用），交由 guard 复核"
            details.append(note)
            return SolveResult(
                True,
                "; ".join(details),
                data={
                    "slider_center": detection.slider_center,
                    "gap_x": gap_x,
                    "distance": detection.distance,
                    "rounds": details,
                },
            )
        return SolveResult(
            False,
            f"滑动 {self._max_rounds} 轮后验证码仍然存在",
            data={"rounds": details},
        )
