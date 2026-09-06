"""Detect and solve QQ Reader / emulator slide CAPTCHAs.

This is a local OpenCV implementation inspired by public slide-CAPTCHA cracking
projects (e.g. ``slide_captcha_cracker`` / ``sliding-captcha``).  It captures the
emulator screen, locates the horizontal slider track and the slider handle,
estimates the target gap by edge projection, then performs a swipe through the
local MaaFramework controller (``maa_click.py --swipe``).

The detector is intentionally conservative: if it cannot find both a track and a
slider handle, it reports ``found=false`` and does not swipe.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MAA_CLICKER = ROOT / "tools" / "maa_click.py"
EMU_MOUSE = ROOT / "tools" / "emu_mouse.py"
EMU_SCREENSHOT = ROOT / "tools" / "emu_screenshot.py"
EXTERNAL_PY = Path(r"D:\python\python.exe")
TARGET_W, TARGET_H = 720, 1280

_OCR_ITEM_RE = re.compile(
    r'\{"box":\[(\d+),(\d+),(\d+),(\d+)\],"score":[0-9.eE+-]+,"text":"((?:\\.|[^"\\])*)"\}'
)


def adb_bytes(adb: Path, device: str, *args: str) -> bytes:
    completed = subprocess.run(
        [str(adb), "-s", device, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return completed.stdout


def _adb_screenshot(adb: Path, device: str) -> tuple[bytes, np.ndarray] | None:
    try:
        data = adb_bytes(adb, device, "exec-out", "screencap", "-p")
    except Exception:
        return None
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        return None
    # A fully black/empty frame usually means FLAG_SECURE blocked ADB.
    if float(np.mean(image)) < 1.0:
        return None
    return data, image


def _window_screenshot() -> tuple[bytes, np.ndarray] | None:
    """Capture the MuMu window via Win32 and resize to 720x1280."""
    if not EMU_SCREENSHOT.exists() or not EXTERNAL_PY.exists():
        return None
    out = ROOT / "dev" / "debug" / "emu_window_latest.png"
    try:
        completed = subprocess.run(
            [str(EXTERNAL_PY), str(EMU_SCREENSHOT), "--output", str(out)],
            cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        parsed = {}
        for line in reversed(completed.stdout.splitlines()):
            try:
                parsed = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
        if not parsed.get("ok") or not out.exists():
            return None
        data = out.read_bytes()
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return None
        h, w = image.shape[:2]
        if w == TARGET_W and h > TARGET_H:
            # MuMu client area usually has a small top toolbar; the Android
            # framebuffer is the lower TARGET_H rows.
            offset = h - TARGET_H
            image = image[offset:offset + TARGET_H, :]
        elif (w, h) != (TARGET_W, TARGET_H):
            image = cv2.resize(image, (TARGET_W, TARGET_H), interpolation=cv2.INTER_AREA)
        return data, image
    except Exception:
        return None


def screenshot(adb: Path, device: str) -> tuple[bytes, np.ndarray]:
    result = _adb_screenshot(adb, device)
    if result is not None:
        return result
    window = _window_screenshot()
    if window is not None:
        return window
    raise RuntimeError("ADB and Windows screenshot both failed")


def find_title_box_from_log(log_path: Path) -> list[int] | None:
    """Find the slide-CAPTCHA title box (e.g. 安全验证) from Maa's OCR log."""
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    candidates = []
    for match in _OCR_ITEM_RE.finditer(text):
        x, y, w, h = map(int, match.groups()[:4])
        raw = match.group(5)
        try:
            parsed = json.loads(f'"{raw}"')
        except json.JSONDecodeError:
            parsed = raw
        value = str(parsed)
        if any(k in value for k in ("安全验证", "拖动", "滑块", "向右滑动")):
            candidates.append((y, [x, y, x + w, y + h]))
    if not candidates:
        return None
    candidates.sort()
    return candidates[-1][1]


def _find_track_and_slider(image: np.ndarray, title_box: list[int] | None = None):
    """Return (track_rect, slider_rect) or (None, None).

    QQ Reader's Tencent slide CAPTCHA inside MuMu uses:
    * a light-gray horizontal track (BGR ~200) inside the white popup card;
    * a blue rounded-rectangle slider handle on that track.

    The old Hough-line approach confused the white card's bottom edge with the
    track and picked up background text/icons as the handle, so this version
    looks for the gray track and the saturated blue handle directly.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    search_y0 = title_box[3] + 10 if title_box else int(h * 0.40)
    search_y0 = max(0, min(search_y0, h - 1))
    search_y1 = h - 60

    # 1) Find the wide light-gray horizontal track.
    best_line = None
    for y in range(search_y0, search_y1):
        row = gray[y, :]
        mask = (row >= 180) & (row <= 220)
        max_run = 0
        run = 0
        start = 0
        best_start = 0
        for x, v in enumerate(mask):
            if v:
                if run == 0:
                    start = x
                run += 1
                if run > max_run:
                    max_run = run
                    best_start = start
            else:
                run = 0
        if max_run > w * 0.40:
            if best_line is None or max_run > best_line[0]:
                best_line = (max_run, best_start, y)
    if best_line is None:
        return None, None

    _, _, peak_y = best_line
    rows = []
    for yy in range(max(0, peak_y - 30), min(h, peak_y + 31)):
        row = gray[yy, :]
        mask = (row >= 180) & (row <= 220)
        max_run = 0
        run = 0
        for v in mask:
            if v:
                run += 1
                max_run = max(max_run, run)
            else:
                run = 0
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
    track = (int(xs.min()), y_top, int(xs.max()) - int(xs.min()) + 1,
             y_bot - y_top + 1)

    # 2) Find the blue rounded-rectangle slider handle on/near the track.
    blue = cv2.inRange(image, (180, 50, 0), (255, 150, 80))
    blue = cv2.morphologyEx(blue, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    slider = None
    track_cy = y_top + (y_bot - y_top) // 2
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cv2.contourArea(cnt)
        if area < 500:
            continue
        if not (60 <= cw <= 180 and 35 <= ch <= 100):
            continue
        if abs((y + ch / 2) - track_cy) > 80:
            continue
        if slider is None or area > cv2.contourArea(slider):
            slider = (x, y, cw, ch)

    if slider is None:
        return track, None
    return track, slider


def _find_gap_x(gray: np.ndarray, track, slider) -> int | None:
    """Estimate the target x by projecting vertical edges in the puzzle area.

    The puzzle image sits above the slider track; the missing-piece notch
    produces a strong vertical edge there.
    """
    x, y, cw, ch = track
    h, w = gray.shape[:2]
    # Puzzle area: focus on the lower part of the puzzle just above the track.
    y1 = max(0, y - 200)
    y2 = max(y1 + 20, y - 30)
    x1 = max(0, x)
    x2 = min(w, x + cw)
    roi = gray[y1:y2, x1:x2]
    if roi.size == 0:
        return None
    edges = cv2.Canny(roi, 50, 150)
    col_density = edges.sum(axis=0) / max(1, edges.shape[0])
    search_start = max(0, slider[0] - x1 + slider[2])
    if search_start >= len(col_density):
        return None
    search = col_density[search_start:]
    if search.size < 10:
        return None
    kernel = np.ones(7, dtype=float) / 7
    smoothed = np.convolve(search, kernel, mode="same")
    idx = int(np.argmax(smoothed))
    peak = smoothed[idx]
    if peak < 1.0:
        return None
    return x1 + search_start + idx


def detect(image_bytes: bytes, image: np.ndarray,
           title_box: list[int] | None = None) -> dict[str, object]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    track, slider = _find_track_and_slider(image, title_box)
    if track is None or slider is None:
        return {"found": False, "error": "未检测到滑块轨道/滑块按钮"}

    gap_x = _find_gap_x(gray, track, slider)
    if gap_x is None:
        return {
            "found": False,
            "error": "未检测到滑块缺口位置",
            "track": [int(v) for v in track],
            "slider": [int(v) for v in slider],
        }

    slider_cx = slider[0] + slider[2] // 2
    slider_cy = slider[1] + slider[3] // 2
    distance = gap_x - slider_cx
    # Sanity check: the drag should move right and be within the track.
    if distance <= 0 or distance > track[2] * 1.5:
        return {
            "found": False,
            "error": f"滑块距离异常：{distance}",
            "track": [int(v) for v in track],
            "slider": [int(v) for v in slider],
            "gap_x": int(gap_x),
        }

    return {
        "found": True,
        "track": [int(v) for v in track],
        "slider": [int(v) for v in slider],
        "slider_center": [int(slider_cx), int(slider_cy)],
        "gap_x": int(gap_x),
        "distance": int(distance),
        "target": [int(slider_cx + int(distance)), int(slider_cy)],
    }


def _run_maa_swipe(adb: Path, device: str, x1: int, y1: int, x2: int, y2: int,
                   duration: int, input_method: str) -> bool:
    if not MAA_CLICKER.exists():
        return False
    try:
        completed = subprocess.run(
            [sys.executable, str(MAA_CLICKER),
             "--adb", str(adb), "--device", device,
             "--swipe", str(x1), str(y1), str(x2), str(y2),
             "--duration", str(duration), "--input-method", input_method],
            cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        parsed = {}
        for line in reversed(completed.stdout.splitlines()):
            try:
                parsed = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
        if parsed.get("ok"):
            return True
    except Exception:
        pass
    return False


def swipe(adb: Path, device: str, x1: int, y1: int, x2: int, y2: int,
          duration: int = 600, external: bool = True,
          input_method: str = "emulator") -> bool:
    # Prefer MaaFramework's maatouch: it is a real touch-channel injection and
    # works on this MuMu (verified: it can close the CAPTCHA popup), while
    # ``adb input swipe`` and synthetic Windows mouse events are ignored.
    if _run_maa_swipe(adb, device, x1, y1, x2, y2, duration, input_method):
        return True

    # Fallback: external mouse simulation on the emulator window.
    if external and EMU_MOUSE.exists() and EXTERNAL_PY.exists():
        try:
            completed = subprocess.run(
                [str(EXTERNAL_PY), str(EMU_MOUSE),
                 "--x1", str(x1), "--y1", str(y1),
                 "--x2", str(x2), "--y2", str(y2),
                 "--duration", str(duration)],
                cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", timeout=30,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            parsed = {}
            for line in reversed(completed.stdout.splitlines()):
                try:
                    parsed = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
            if parsed.get("ok"):
                return True
        except Exception:
            pass

    # Fallback: MAA controller with adb shell input.
    if _run_maa_swipe(adb, device, x1, y1, x2, y2, duration, "adb"):
        return True

    # Last resort: adb swipe.
    try:
        adb_bytes(adb, device, "shell", "input", "swipe",
                  str(x1), str(y1), str(x2), str(y2), str(duration))
        time.sleep(1.0)
        return True
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", type=Path,
                        default=Path(r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"))
    parser.add_argument("--device", default="127.0.0.1:16385")
    parser.add_argument("--image", type=Path,
                        help="use a local screenshot instead of ADB capture")
    parser.add_argument("--log", type=Path,
                        help="MaaFramework maafw.log used to locate the 安全验证 title")
    parser.add_argument("--output", type=Path,
                        help="write annotated screenshot")
    parser.add_argument("--swipe", action="store_true",
                        help="perform the swipe after detection")
    parser.add_argument("--external", action="store_true", default=True,
                        help="use external mouse simulation on the emulator window")
    parser.add_argument("--input-method", choices=("adb", "maatouch", "minitouch", "emulator"),
                        default="emulator",
                        help="Maa ADB input method for the swipe")
    args = parser.parse_args()

    if args.image:
        data = args.image.read_bytes()
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            print(json.dumps({"found": False, "error": f"无法读取图片：{args.image}"}))
            return 2
    else:
        data, image = screenshot(args.adb, args.device)

    title_box = find_title_box_from_log(args.log) if args.log and args.log.exists() else None
    result = detect(data, image, title_box)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        marked = image.copy()
        if result.get("found"):
            track = result["track"]
            slider = result["slider"]
            cv2.rectangle(marked, (track[0], track[1]),
                          (track[0] + track[2], track[1] + track[3]), (0, 255, 0), 2)
            cv2.rectangle(marked, (slider[0], slider[1]),
                          (slider[0] + slider[2], slider[1] + slider[3]), (255, 0, 0), 2)
            cv2.line(marked, tuple(result["slider_center"]),
                     tuple(result["target"]), (0, 0, 255), 2)
        cv2.imwrite(str(args.output), marked)
        result["output"] = str(args.output)

    if args.swipe and result.get("found"):
        sx, sy = result["slider_center"]
        tx, ty = result["target"]
        result["swiped"] = swipe(args.adb, args.device, sx, sy, tx, ty,
                                 external=args.external,
                                 input_method=args.input_method)

    print(json.dumps(result, ensure_ascii=False))
    return 0 if (not args.swipe or result.get("swiped")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
