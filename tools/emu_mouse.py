"""Simulate a mouse drag on the MuMu emulator window using Windows APIs.

Some slide CAPTCHAs detect ``adb input swipe`` as automation.  This module maps
Android logical coordinates (720x1280) to the MuMu window's client area and
performs a human-like mouse drag with ``SetCursorPos`` / ``mouse_event``.

Usage::

    python emu_mouse.py --x1 120 --y1 650 --x2 420 --y2 650 --duration 800
"""

from __future__ import annotations

import argparse
import ctypes
import json
import time
from ctypes import wintypes

import win32con
import win32gui


def find_emulator_window() -> tuple[int, str] | None:
    """Find a visible MuMu emulator window."""
    candidates = []
    def collect(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd).strip()
        if any(k in title for k in ("碧蓝航线", "MuMu", "MuMuPlayer", "QQ 阅读")):
            rect = win32gui.GetWindowRect(hwnd)
            area = max(0, rect[2] - rect[0]) * max(0, rect[3] - rect[1])
            if area > 10000:
                candidates.append((area, hwnd, title))
        return True
    win32gui.EnumWindows(collect, None)
    if not candidates:
        return None
    _, hwnd, title = max(candidates)
    return hwnd, title


def activate_window(hwnd: int) -> None:
    """Try to bring the emulator window to the foreground before mouse input."""
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        win32gui.BringWindowToTop(hwnd)
    except Exception:
        pass


def android_to_screen(hwnd: int, x: int, y: int,
                      android_w: int = 720, android_h: int = 1280) -> tuple[int, int]:
    """Map Android logical coords to screen coords inside the client area.

    MuMu's client area can be taller than the Android framebuffer because it
    includes a small window toolbar at the top.  When the client width equals
    the Android width, treat the extra height as a top offset instead of
    scaling the whole image (which would put the cursor above the real widget).
    """
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    cw = max(1, right - left)
    ch = max(1, bottom - top)
    origin = win32gui.ClientToScreen(hwnd, (0, 0))
    if cw == android_w and ch > android_h:
        offset_y = ch - android_h
        sx = origin[0] + x
        sy = origin[1] + offset_y + y
    else:
        sx = origin[0] + int(x / android_w * cw)
        sy = origin[1] + int(y / android_h * ch)
    return sx, sy


def mouse_drag(x1: int, y1: int, x2: int, y2: int, duration_ms: int = 800) -> bool:
    """Drag the mouse from (x1,y1) to (x2,y2) in screen coordinates."""
    user32 = ctypes.windll.user32
    steps = max(10, int(duration_ms / 16))
    user32.SetCursorPos(x1, y1)
    time.sleep(0.05)
    user32.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    for i in range(1, steps + 1):
        t = i / steps
        # Ease-out curve to look more human.
        eased = 1 - (1 - t) ** 2
        cx = int(x1 + (x2 - x1) * eased)
        cy = int(y1 + (y2 - y1) * eased)
        user32.SetCursorPos(cx, cy)
        time.sleep(duration_ms / 1000 / steps)
    time.sleep(0.05)
    user32.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--x1", type=int, required=True)
    parser.add_argument("--y1", type=int, required=True)
    parser.add_argument("--x2", type=int, required=True)
    parser.add_argument("--y2", type=int, required=True)
    parser.add_argument("--duration", type=int, default=800)
    args = parser.parse_args()

    found = find_emulator_window()
    if found is None:
        print(json.dumps({"ok": False, "error": "未找到 MuMu 模拟器窗口"}))
        return 1
    hwnd, title = found
    activate_window(hwnd)
    time.sleep(0.15)
    sx1, sy1 = android_to_screen(hwnd, args.x1, args.y1)
    sx2, sy2 = android_to_screen(hwnd, args.x2, args.y2)
    ok = mouse_drag(sx1, sy1, sx2, sy2, args.duration)
    print(json.dumps({
        "ok": ok,
        "window": title,
        "screen_from": [sx1, sy1],
        "screen_to": [sx2, sy2],
    }, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
