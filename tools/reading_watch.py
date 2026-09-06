"""Drive the QQ Reader reading task outside Maa.

QQ Reader's reader page (``ReaderPageActivity``) **forbids ADB screencap**, so
the Maa pipeline cannot run any node (recognition or plain action) once it is
inside the book: every node entry tries to screencap and fails.  The reading
task only needs the reader page to stay open and turn pages for ~10 minutes,
which Maa structurally cannot do.

This watcher fills that gap:

1. Detects when the reader page comes to the foreground.
2. While it is foreground, taps a page-turn spot (right side of the screen)
   every ``--interval`` seconds so reading time accumulates.
3. After ``--minutes`` minutes in the reader, presses BACK twice to return to
   the QQ Reader main UI (which is screenshot-able again, so Maa can resume).

It never needs a screenshot, so the screencap ban on the reader page is a
non-issue.

Usage::

    python reading_watch.py --adb <adb.exe> --device 127.0.0.1:16385 \
        --minutes 11 --interval 30

Prints a JSON summary line at the end.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path

READER_ACTIVITY = re.compile(r"ReaderPageActivity|CommonSimpleFlutterActivity")
READER_APP = re.compile(r"com\.qq\.reader")
MAIN_ACTIVITY = re.compile(r"MainFlutterActivity")
BACK_KEY = "4"


def adb(adb: Path, device: str, *args: str) -> str:
    try:
        completed = subprocess.run(
            [str(adb), "-s", device, *args],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return completed.stdout.decode("utf-8", errors="replace")
    except Exception:
        return ""


def foreground(adb_path: Path, device: str) -> str:
    for line in adb(adb_path, device, "shell", "dumpsys", "window").splitlines():
        if "mCurrentFocus" in line:
            return line
    return ""


def is_reader_page(adb_path: Path, device: str) -> bool:
    """True while we are inside the reading session.

    Turning pages can momentarily land on an interstitial ad webview inside
    QQ Reader (``WebBrowserForFullScreenContents``), and the Flutter reader
    may flip between ReaderPageActivity / CommonSimpleFlutterActivity.  All of
    those still count as "inside the book" — we keep turning pages.  Only two
    states end the session: leaving the QQ Reader app entirely, or returning
    to the main UI (MainFlutterActivity)."""
    line = foreground(adb_path, device)
    if not READER_APP.search(line):
        return False
    if MAIN_ACTIVITY.search(line):
        return False
    return True


def tap(adb: Path, device: str, x: int, y: int) -> bool:
    try:
        subprocess.run(
            [str(adb), "-s", device, "shell", "input", "tap", str(x), str(y)],
            check=False, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except Exception:
        return False


def press_back(adb_path: Path, device: str, n: int = 1, settle: float = 1.2) -> None:
    for _ in range(n):
        adb(adb_path, device, "shell", "input", "keyevent", BACK_KEY)
        time.sleep(settle)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", type=Path, required=True)
    parser.add_argument("--device", default="127.0.0.1:16385")
    parser.add_argument("--minutes", type=float, default=11.0,
                        help="how long to stay in the reader page (default 11)")
    parser.add_argument("--interval", type=float, default=30.0,
                        help="seconds between page-turn taps (default 30)")
    parser.add_argument("--tap-point", nargs=2, type=int, default=(600, 640),
                        metavar=("X", "Y"), help="page-turn tap position")
    parser.add_argument("--timeout", type=float, default=40.0,
                        help="seconds to wait for the reader page to appear "
                             "before giving up")
    args = parser.parse_args()

    target = args.minutes * 60.0
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        if is_reader_page(args.adb, args.device):
            break
        time.sleep(1.0)
    else:
        print(json.dumps({"ok": False, "error": "reader page did not appear",
                          "activity": foreground(args.adb, args.device)}))
        return 2

    entered = time.monotonic()
    taps = 0
    last_tap = 0.0
    while time.monotonic() - entered < target:
        elapsed = time.monotonic() - entered
        if not is_reader_page(args.adb, args.device):
            print(json.dumps({
                "ok": False, "error": "left reader page early",
                "elapsed": round(elapsed), "taps": taps,
                "activity": foreground(args.adb, args.device)}))
            return 3
        if time.monotonic() - last_tap >= args.interval:
            tap(args.adb, args.device, *args.tap_point)
            taps += 1
            last_tap = time.monotonic()
            print(f"[{time.strftime('%H:%M:%S')}] reader page: {int(elapsed)}s "
                  f"elapsed, tap #{taps}", flush=True)
        time.sleep(2.0)

    press_back(args.adb, args.device, 2)
    print(json.dumps({
        "ok": True,
        "elapsed": int(time.monotonic() - entered),
        "taps": taps,
        "activity_after": foreground(args.adb, args.device),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
