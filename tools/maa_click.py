"""Click or swipe emulator coordinates through a local MaaFramework ADB controller.

The CAPTCHA solver needs to tap a list of (x, y) points in a fixed order, and
the slide-CAPTCHA solver needs to drag from one point to another.  This module
wraps MaaFramework's ``MaaControllerPostClick`` / ``MaaControllerPostSwipe`` so
those actions go through the same ADB controller Maa uses.

Usage (as a subprocess):

    # taps
    python maa_click.py --adb <adb.exe> --device 127.0.0.1:16384 \
        --point 300 800 --point 320 900

    # swipe (slide CAPTCHA)
    python maa_click.py --adb <adb.exe> --device 127.0.0.1:16384 \
        --swipe 150 650 420 650 --duration 600

It prints one JSON line per action result and a final summary.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import time
from pathlib import Path


STATUS_SUCCEEDED = 3000
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# MaaDef.h
MaaCtrlOption_ScreenshotTargetShortSide = 2

# MaaAdbScreencapMethod_Encode | MaaAdbInputMethod_AdbShell (matches the
# Naruto clicker; we only need the controller for input, not its screencap).
SCREENCAP_METHODS = 1 << 1
INPUT_METHODS = 1  # MaaAdbInputMethod_AdbShell


def _b(value: str | Path) -> bytes:
    return os.fsencode(os.fspath(value))


class MaaCoordClicker:
    """A minimal MaaFramework ADB controller that posts coordinate clicks."""

    INPUT_METHODS = {
        "adb": 1,                    # MaaAdbInputMethod_AdbShell
        "minitouch": 1 << 1,         # MaaAdbInputMethod_MinitouchAndAdbKey
        "maatouch": 1 << 2,          # MaaAdbInputMethod_Maatouch
        "emulator": 1 << 3,          # MaaAdbInputMethod_EmulatorExtras
    }

    def __init__(self, runtime: Path, adb: Path, device: str,
                 input_method: str = "adb", extra_config: str = "{}") -> None:
        self.runtime = runtime
        self.adb = adb
        self.device = device
        self.input_method = input_method
        if input_method == "emulator" and (not extra_config or extra_config == "{}"):
            # MuMu EmulatorExtras expects a nested ``extras.mumu`` config.
            import json as _json
            extra_config = _json.dumps({
                "extras": {
                    "mumu": {
                        "enable": True,
                        "path": r"D:\Program Files\Netease\MuMu Player 12",
                    }
                }
            }, ensure_ascii=False)
        self.extra_config = extra_config
        # MuMu runs its own ADB server on 5038.  Set it before the DLL is
        # loaded so the ADB controller talks to the right server.
        self._dll_dir = os.add_dll_directory(str(runtime))
        self.lib = ctypes.CDLL(str(runtime / "MaaFramework.dll"))
        self.controller = ctypes.c_void_p()
        self._configure_api()

    def _configure_api(self) -> None:
        lib = self.lib
        lib.MaaAdbControllerCreate.argtypes = [
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint64, ctypes.c_uint64,
            ctypes.c_char_p, ctypes.c_char_p]
        lib.MaaAdbControllerCreate.restype = ctypes.c_void_p
        lib.MaaControllerSetOption.argtypes = [
            ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p, ctypes.c_uint64]
        lib.MaaControllerSetOption.restype = ctypes.c_uint8
        lib.MaaControllerPostConnection.argtypes = [ctypes.c_void_p]
        lib.MaaControllerPostConnection.restype = ctypes.c_int64
        lib.MaaControllerPostClick.argtypes = [
            ctypes.c_void_p, ctypes.c_int32, ctypes.c_int32]
        lib.MaaControllerPostClick.restype = ctypes.c_int64
        lib.MaaControllerPostSwipe.argtypes = [
            ctypes.c_void_p, ctypes.c_int32, ctypes.c_int32,
            ctypes.c_int32, ctypes.c_int32, ctypes.c_int32]
        lib.MaaControllerPostSwipe.restype = ctypes.c_int64
        lib.MaaControllerWait.argtypes = [ctypes.c_void_p, ctypes.c_int64]
        lib.MaaControllerWait.restype = ctypes.c_int32
        lib.MaaControllerDestroy.argtypes = [ctypes.c_void_p]

    def connect(self) -> None:
        ctrl = self.lib.MaaAdbControllerCreate(
            _b(self.adb), self.device.encode("utf-8"),
            SCREENCAP_METHODS, self.INPUT_METHODS[self.input_method],
            self.extra_config.encode("utf-8"),
            _b(self.runtime / "MaaAgentBinary"))
        self.controller = ctypes.c_void_p(ctrl)
        if not self.controller.value:
            raise RuntimeError("MaaAdbControllerCreate failed")
        # Preserve the 720p coordinate system used by the CAPTCHA screenshots.
        short_side = ctypes.c_int32(720)
        self.lib.MaaControllerSetOption(
            self.controller, MaaCtrlOption_ScreenshotTargetShortSide,
            ctypes.byref(short_side), ctypes.sizeof(short_side))
        conn_id = self.lib.MaaControllerPostConnection(self.controller)
        status = self.lib.MaaControllerWait(self.controller, conn_id)
        if status != STATUS_SUCCEEDED:
            raise RuntimeError(f"MAA controller connection failed: {status}")

    def click(self, x: int, y: int, settle: float = 0.65) -> tuple[bool, str]:
        """Post a single click at ``(x, y)`` and wait for it to finish."""
        task_id = self.lib.MaaControllerPostClick(
            self.controller, int(x), int(y))
        if task_id == 0:
            return False, f"MAA rejected click at ({x}, {y})"
        status = self.lib.MaaControllerWait(self.controller, task_id)
        if status == STATUS_SUCCEEDED:
            if settle > 0:
                time.sleep(settle)
            return True, f"MAA clicked ({x}, {y})"
        return False, f"MAA click at ({x}, {y}) failed (status {status})"

    def swipe(self, x1: int, y1: int, x2: int, y2: int,
              duration: int = 600, settle: float = 0.8) -> tuple[bool, str]:
        """Post a swipe from (x1,y1) to (x2,y2) and wait for it to finish."""
        task_id = self.lib.MaaControllerPostSwipe(
            self.controller, int(x1), int(y1), int(x2), int(y2), int(duration))
        if task_id == 0:
            return False, f"MAA rejected swipe ({x1},{y1})->({x2},{y2})"
        status = self.lib.MaaControllerWait(self.controller, task_id)
        if status == STATUS_SUCCEEDED:
            if settle > 0:
                time.sleep(settle)
            return True, f"MAA swiped ({x1},{y1})->({x2},{y2})"
        return False, f"MAA swipe ({x1},{y1})->({x2},{y2}) failed (status {status})"

    def close(self) -> None:
        if self.controller.value:
            self.lib.MaaControllerDestroy(self.controller)
            self.controller = ctypes.c_void_p()
        try:
            self._dll_dir.close()
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path,
                        default=PROJECT_ROOT / "dev")
    parser.add_argument("--adb", type=Path,
                        default=Path(r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"))
    parser.add_argument("--device", default="127.0.0.1:16385")
    parser.add_argument("--point", action="append", nargs=2, type=int,
                        metavar=("X", "Y"), help="coordinate to click; repeatable")
    parser.add_argument("--swipe", nargs=4, type=int,
                        metavar=("X1", "Y1", "X2", "Y2"),
                        help="perform one swipe instead of clicks")
    parser.add_argument("--duration", type=int, default=600,
                        help="swipe duration in milliseconds")
    parser.add_argument("--settle", type=float, default=0.65,
                        help="seconds to wait after each tap/swipe")
    parser.add_argument("--input-method", choices=("adb", "maatouch", "minitouch", "emulator"),
                        default="adb",
                        help="Maa ADB input method to use (default: adb shell)")
    parser.add_argument("--extra-config", default="{}",
                        help="JSON config passed to MaaAdbControllerCreate (e.g. MuMu extras path)")
    parser.add_argument("--submit", action="store_true",
                        help="accepted for symmetry with the solver; no-op here")
    args = parser.parse_args()

    if not args.point and not args.swipe:
        print(json.dumps({"ok": False, "error": "no --point or --swipe given"}))
        return 2
    clicker = MaaCoordClicker(args.runtime, args.adb, args.device,
                              input_method=args.input_method,
                              extra_config=args.extra_config)
    results = []
    ok_all = True
    try:
        clicker.connect()
        if args.swipe:
            x1, y1, x2, y2 = args.swipe
            ok, message = clicker.swipe(x1, y1, x2, y2, args.duration, args.settle)
            results.append({"action": "swipe", "ok": ok, "message": message})
            ok_all = ok
        else:
            for x, y in args.point:
                ok, message = clicker.click(x, y, args.settle)
                results.append({"x": x, "y": y, "ok": ok, "message": message})
                ok_all = ok_all and ok
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc), "results": results}))
        return 2
    finally:
        clicker.close()
    print(json.dumps({"ok": ok_all, "results": results}, ensure_ascii=False))
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
