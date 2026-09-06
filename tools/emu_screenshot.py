"""Capture the MuMu emulator window via Win32 as a fallback screenshot method.

QQ Reader can mark the reading/ad page as FLAG_SECURE, which makes ADB
``screencap`` return an empty/black frame.  This tool captures the visible MuMu
window directly from Windows using ``PrintWindow``, which bypasses the Android
secure-screen restriction.

Usage::

    python emu_screenshot.py --output out.png
"""

from __future__ import annotations

import argparse
import ctypes
import json
from ctypes import wintypes

import win32con
import win32gui
from PIL import Image, ImageGrab


def find_emulator_window() -> tuple[int, str] | None:
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


def capture_window(hwnd: int, output: str) -> tuple[int, int]:
    """Capture the window client area to a PNG. Returns (client_w, client_h)."""
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    w = max(1, right - left)
    h = max(1, bottom - top)

    # Use PrintWindow with PW_RENDERFULLCONTENT when available.
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32gui.CreateCompatibleDC(hwnd_dc)
    bmp = win32gui.CreateCompatibleBitmap(hwnd_dc, w, h)
    win32gui.SelectObject(mfc_dc, bmp)
    try:
        result = ctypes.windll.user32.PrintWindow(hwnd, mfc_dc, 2)  # PW_RENDERFULLCONTENT
        if result == 0:
            # Fallback: capture the screen region of the window.
            screen_rect = win32gui.GetWindowRect(hwnd)
            img = ImageGrab.grab(
                bbox=(screen_rect[0], screen_rect[1], screen_rect[2], screen_rect[3]))
        else:
            buf = ctypes.create_string_buffer(w * h * 4)
            ctypes.windll.gdi32.GetBitmapBits(int(bmp), len(buf), buf)
            img = Image.frombuffer("RGB", (w, h), buf.raw, "raw", "BGRX", 0, 1)
    finally:
        win32gui.DeleteObject(bmp)
        win32gui.DeleteDC(mfc_dc)
        win32gui.ReleaseDC(hwnd, hwnd_dc)
    img.save(output)
    return w, h


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    found = find_emulator_window()
    if found is None:
        print(json.dumps({"ok": False, "error": "未找到 MuMu 模拟器窗口"}))
        return 1
    hwnd, title = found
    try:
        w, h = capture_window(hwnd, args.output)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    print(json.dumps({"ok": True, "window": title, "output": args.output,
                      "size": [w, h]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
