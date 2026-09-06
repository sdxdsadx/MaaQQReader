"""Run the configured Maa ad task and automatically handle CAPTCHAs / missing ads.

This supervisor keeps MaaPiCli running the DailyAdFlow.  It watches maafw.log
for:

* ``AdCaptchaDetected`` -> solve and submit the ordered-image CAPTCHA.
* ``AdClickWatch``/``AdVideoCounterVisible``/``AdScrollToVideoCard`` failures ->
  locate the QQ Reader ad card ("ad div") from Maa's latest OCR boxes and click
  the "立即观看" button inside it through the local MaaFramework controller.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

import captcha_solver
import slide_captcha_solver


ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "dev"
LOG = DEV / "debug" / "maafw.log"
SOLVER = ROOT / "tools" / "captcha_solver.py"
SLIDE_SOLVER = ROOT / "tools" / "slide_captcha_solver.py"
AD_LOCATOR = ROOT / "tools" / "ad_locator.py"
AD_CLOSE_FINDER = ROOT / "tools" / "ad_close_finder.py"
RUNNER = ROOT / "tools" / "run_maa_ad.py"
PYTHON = ROOT / ".venv-captcha" / "Scripts" / "python.exe"
ADB = Path(r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe")
DEVICE = "127.0.0.1:16385"
# Position of the challenge popup's refresh icon (lower-left of the popup).
# Pulled out as a constant so the solver and supervisor agree on the target.
REFRESH_POINT = (180, 908)
REFRESH_SETTLE = 1.6
# Cross-call counter: consecutive non-challenge (stale) CAPTCHA frames.  A real
# submit resets it; too many in a row means the challenge keeps being misread
# and the supervisor should escalate instead of reporting "handled" forever.
STALE_CAPTCHA = 0

# Maa log signals that mean "an ad just ended / the flow returned to the reward
# page".  Right after these we screenshot and classify click-vs-slide CAPTCHA.
# We require a real Node success event, not just a recognition attempt for a
# node named AdDailyComplete (that name appears constantly during OCR scans).
_POST_AD_RE = re.compile(
    r'msg=Node\.(?:PipelineNode|NextList)\.Succeeded.*"name":"(?:AdDailyRepeat|AdReturnStable|AdCompleted|AdDailyComplete|LevelAfterAd)"'
)
POST_AD_CHECK_INTERVAL = 4.0


def _tap_refresh_control() -> None:
    """Tap the challenge popup's refresh control.  We use this both when the
    solver says the current frame is stale and when a solve was submitted but
    the popup is still on screen (which means the answer was wrong, or the
    click landed on a stale coordinate, and the best recovery is a fresh
    challenge)."""
    try:
        subprocess.run(
            [str(ADB), "-s", DEVICE, "shell", "input", "tap",
             str(REFRESH_POINT[0]), str(REFRESH_POINT[1])],
            check=False, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        pass
    time.sleep(REFRESH_SETTLE)


def solve_captcha() -> bool:
    """Try to clear the current CAPTCHA popup and report whether we succeeded.

    The flow matches the v2 solver contract:

    * ``captcha_layout: false``  — the solver decided the frame was not a
      challenge popup at all.  Increment a stale counter (so a run-away
      AdCaptchaDetected stream eventually escalates) and pretend the event
      was handled so Maa can advance.
    * ``submitted: true`` + ``captcha_still_visible: false`` — the popup
      closed after our taps.  Real success, return True.
    * ``submitted: true`` + ``captcha_still_visible: true`` — our answer was
      wrong (or the click missed).  The popup is still there, so refreshing
      the challenge is the safe move.  We do **not** claim success and we do
      **not** increment the stale counter, because the popup really is there.
    * ``submitted: false`` / ``refresh_recommended: true`` — the solver
      itself gave up on this frame (stuck, no-op clicks, ambiguous, etc).
      Treat as a soft failure and refresh the challenge before retrying.

    On any failure path we refresh the challenge and loop; the supervisor's
    outer 30-attempt budget still bounds the total time so a permanent
    failure (Maa firing AdCaptchaDetected on a non-challenge frame forever)
    eventually escalates.
    """
    global STALE_CAPTCHA
    for attempt in range(1, 31):
        try:
            raw = subprocess.run(
                [str(ADB), "-s", DEVICE, "exec-out", "screencap", "-p"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True,
                timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ).stdout
            (DEV / "debug" / f"captcha_attempt_{attempt}.png").write_bytes(raw)
        except Exception:
            pass
        try:
            result = subprocess.run(
                [str(PYTHON), str(SOLVER), "--adb", str(ADB), "--device", DEVICE,
                 "--submit", "--click-engine", "adb"],
                cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", timeout=120,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            output = result.stdout.strip()
        except subprocess.TimeoutExpired:
            print(f"[{datetime.now():%H:%M:%S}] CAPTCHA solver timed out; refreshing challenge", flush=True)
            _tap_refresh_control()
            continue
        except Exception as exc:
            print(f"[{datetime.now():%H:%M:%S}] CAPTCHA solver error: {exc}; refreshing", flush=True)
            _tap_refresh_control()
            continue
        print(f"[{datetime.now():%H:%M:%S}] CAPTCHA attempt {attempt}: {output[-500:]}", flush=True)
        try:
            parsed = json.loads(output.splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            parsed = {}
        if parsed.get("captcha_layout") is False:
            STALE_CAPTCHA += 1
            print(f"[{datetime.now():%H:%M:%S}] stale CAPTCHA event ({STALE_CAPTCHA}); "
                  f"waiting for a stable challenge frame", flush=True)
            if STALE_CAPTCHA >= 8:
                print(f"[{datetime.now():%H:%M:%S}] too many stale CAPTCHA frames; "
                      f"escalating instead of looping", flush=True)
                return False
            return True
        submitted = bool(parsed.get("submitted"))
        still_visible = bool(parsed.get("captcha_still_visible"))
        refresh_requested = bool(parsed.get("refresh_recommended"))
        if submitted and not still_visible:
            # Real success — the popup closed.  Reset stale counter and let
            # Maa resume from the next pipeline node.
            STALE_CAPTCHA = 0
            return True
        if submitted and still_visible:
            # The popup is still there, so the answer was rejected.  Refresh
            # the challenge and try again; do NOT report success, or Maa will
            # re-fire AdCaptchaDetected immediately and we'll loop forever.
            print(f"[{datetime.now():%H:%M:%S}] CAPTCHA submit was rejected; "
                  f"refreshing challenge", flush=True)
        elif refresh_requested:
            print(f"[{datetime.now():%H:%M:%S}] CAPTCHA solver asked for a refresh "
                  f"(stuck frame / no-op click)", flush=True)
        else:
            # No submit, no refresh hint — solver bailed without a clear
            # reason (e.g. ambiguous assignment).  Refresh and retry.
            print(f"[{datetime.now():%H:%M:%S}] CAPTCHA solver could not commit; "
                  f"refreshing challenge", flush=True)
        _tap_refresh_control()
    return False


def locate_ad() -> bool:
    """Locate the QQ Reader ad div/button from the latest Maa OCR log and click it."""
    result = subprocess.run(
        [str(PYTHON), str(AD_LOCATOR), "--log", str(LOG),
         "--adb", str(ADB), "--device", DEVICE,
         "--click", "--click-engine", "adb", "--swipe-up", "3"],
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", timeout=60,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    output = result.stdout.strip()
    print(f"[{datetime.now():%H:%M:%S}] AD locate result: {output[-500:]}", flush=True)
    try:
        parsed = json.loads(output.splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return False
    return bool(parsed.get("found") and parsed.get("clicked"))


def solve_slide_captcha() -> bool:
    """Detect and swipe a slide CAPTCHA through the local MaaFramework controller."""
    if not SLIDE_SOLVER.exists():
        return False
    result = subprocess.run(
        [str(PYTHON), str(SLIDE_SOLVER),
         "--adb", str(ADB), "--device", DEVICE, "--log", str(LOG), "--swipe"],
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", timeout=45,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    output = result.stdout.strip()
    print(f"[{datetime.now():%H:%M:%S}] SLIDE solve result: {output[-500:]}", flush=True)
    try:
        parsed = json.loads(output.splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return False
    return bool(parsed.get("found") and parsed.get("swiped"))


def capture_slide_evidence() -> Path | None:
    """Save the current screen to a timestamped file for slide-CAPTCHA tuning."""
    try:
        raw = subprocess.run(
            [str(ADB), "-s", DEVICE, "exec-out", "screencap", "-p"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True,
            timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout
        if not raw.startswith(b"\x89PNG"):
            return None
        path = DEV / "debug" / f"slide_evidence_{datetime.now():%Y%m%d_%H%M%S}.png"
        path.write_bytes(raw)
        print(f"[{datetime.now():%H:%M:%S}] slide evidence saved: {path}", flush=True)
        return path
    except Exception as exc:
        print(f"[{datetime.now():%H:%M:%S}] slide evidence capture failed: {exc}", flush=True)
        return None


def classify_captcha_from_screen() -> str:
    """Screenshot the current page and decide: ``slide``, ``click`` or ``none``.

    This is the entry point for the post-ad check.  It prefers the slide solver's
    blue-slider detector, then falls back to the click-CAPTCHA popup heuristic.
    """
    try:
        data, image = slide_captcha_solver.screenshot(ADB, DEVICE)
    except Exception as exc:
        print(f"[{datetime.now():%H:%M:%S}] screenshot for captcha classification failed: {exc}", flush=True)
        return "none"

    try:
        result = slide_captcha_solver.detect(data, image)
        if result.get("found"):
            return "slide"
    except Exception as exc:
        print(f"[{datetime.now():%H:%M:%S}] slide detection failed: {exc}", flush=True)

    try:
        # The reward page also has big blue buttons, so we do not rely on the
        # color-only popup heuristic.  Running analyze() is the reliable signal:
        # it only returns a layout when real prompt/target icons are present.
        result = captcha_solver.analyze(data, image)
        if result.get("prompts") and result.get("targets"):
            return "click"
    except Exception:
        # RuntimeError here means "not a click-CAPTCHA layout".
        pass

    return "none"


def check_post_ad_captcha() -> None:
    """After an ad ends, screenshot and handle whichever CAPTCHA is present."""
    kind = classify_captcha_from_screen()
    print(f"[{datetime.now():%H:%M:%S}] post-ad screenshot classify: {kind}", flush=True)
    if kind == "slide":
        capture_slide_evidence()
        if solve_slide_captcha():
            print(f"[{datetime.now():%H:%M:%S}] post-ad slide CAPTCHA solved", flush=True)
        else:
            print(f"[{datetime.now():%H:%M:%S}] post-ad slide CAPTCHA not confirmed", flush=True)
    elif kind == "click":
        if solve_captcha():
            print(f"[{datetime.now():%H:%M:%S}] post-ad click CAPTCHA solved", flush=True)
        else:
            print(f"[{datetime.now():%H:%M:%S}] post-ad click CAPTCHA not confirmed", flush=True)
    else:
        print(f"[{datetime.now():%H:%M:%S}] post-ad no CAPTCHA detected", flush=True)


def captcha_signal(text: str) -> bool:
    """True only when an actual AdCaptchaDetected recognition succeeded."""
    for line in text.splitlines():
        if "Node.Recognition.Succeeded" in line and '"name":"AdCaptchaDetected"' in line:
            return True
    return False


def ad_not_found_signal(text: str) -> bool:
    """Return True when Maa's log shows it failed to find the ad entry."""
    for line in text.splitlines():
        if "max_hit reached" in line and '"name":"AdScrollToVideoCard"' in line:
            return True
        if "Node.Recognition.Failed" in line:
            if '"name":"AdClickWatch"' in line or '"name":"AdVideoCounterVisible"' in line:
                return True
    return False


def ad_close_stuck_signal(text: str) -> bool:
    """True when Maa stalled because the ad page's close (X) button could not
    be found.

    The Pangle (穿山甲) full-screen ad pages have no OCR-able text, so Maa's
    OCR-based close nodes (``AdClosableAfterCountdown`` / ``AdCloseByBackKey``)
    time out and the pipeline dies.  We detect that here so the supervisor can
    step in with the image-based close finder instead.
    """
    for line in text.splitlines():
        if "Node.PipelineNode.Failed" in line and (
            '"name":"AdClosableAfterCountdown"' in line
            or '"name":"AdCloseByBackKey"' in line
        ):
            return True
        if "Task timeout" in line and (
            "AdClosableAfterCountdown" in line or "AdCloseByBackKey" in line
        ):
            return True
    return False


def shelf_nav_stuck_signal(text: str) -> bool:
    """True when Maa cannot get from the QQ Reader shelf into the reward page."""
    for line in text.splitlines():
        if ("Node.PipelineNode.Failed" in line
                and '"name":"AdShelfRewardBanner"' in line):
            return True
        if ("Task timeout" in line and "AdShelfRewardBanner" in line):
            return True
        if ("Node.Recognition.Failed" in line
                and '"name":"AdOpenRewardFromShelf"' in line):
            return True
    return False


def tap_shelf_tab() -> bool:
    """Restart QQ Reader from a clean state, return to shelf, open reward card.

    DailyAdFlow can resume inside a FLAG_SECURE reading page where Back does not
    leave the reader.  Force-stopping and relaunching the app is the reliable way
    to get back to the shelf, then tap the top duration-reward card.
    """
    try:
        adb_bytes(ADB, DEVICE, "shell", "am", "force-stop", "com.qq.reader")
        time.sleep(1.0)
        adb_bytes(ADB, DEVICE, "shell", "monkey", "-p", "com.qq.reader",
                  "-c", "android.intent.category.LAUNCHER", "1")
        time.sleep(4.0)
        # QQ Reader can restore the last reading page even after force-stop.
        # Tap the top-left back arrow ("< 第1章 日常") to leave the reader.
        adb_bytes(ADB, DEVICE, "shell", "input", "tap", "50", "28")
        time.sleep(1.2)
        adb_bytes(ADB, DEVICE, "shell", "input", "tap", "50", "28")
        time.sleep(1.2)
        adb_bytes(ADB, DEVICE, "shell", "input", "tap", "80", "1250")
        time.sleep(1.5)
        adb_bytes(ADB, DEVICE, "shell", "input", "tap", "173", "196")
        time.sleep(2.5)
        return True
    except Exception:
        return False


def tap_reward_banner() -> bool:
    """Tap the shelf '本周阅读时长/领赠币' banner to enter the reward page."""
    try:
        adb_bytes(ADB, DEVICE, "shell", "input", "tap", "173", "196")
        time.sleep(2.5)
        return True
    except Exception:
        return False


def force_close_ad(back_fallback: bool = True) -> bool:
    """Locate the ad X button with the image finder and tap it.

    Returns True when the ad page is gone afterwards.  When the finder cannot
    locate an X (or the tap did not dismiss the page) and ``back_fallback``
    is set, presses the BACK key and re-checks.
    """
    result = subprocess.run(
        [str(PYTHON), str(AD_CLOSE_FINDER), "--adb", str(ADB), "--device", DEVICE,
         "--click"],
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", timeout=60,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    output = result.stdout.strip()
    print(f"[{datetime.now():%H:%M:%S}] ad close finder: {output[-300:]}", flush=True)
    try:
        parsed = json.loads(output.splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        parsed = {}
    if parsed.get("clicked") and parsed.get("still_visible") is False:
        return True
    if back_fallback:
        try:
            subprocess.run(
                [str(ADB), "-s", DEVICE, "shell", "input", "keyevent", "4"],
                check=False, timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            pass
        time.sleep(1.5)
        probe = subprocess.run(
            [str(PYTHON), str(AD_CLOSE_FINDER), "--adb", str(ADB), "--device", DEVICE],
            cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            probe_json = json.loads(probe.stdout.strip().splitlines()[-1])
            return bool(probe_json.get("still_visible") is False)
        except Exception:
            return False
    return False


READING_WATCH = ROOT / "tools" / "reading_watch.py"
READER_ACTIVITY_RE = re.compile(r"ReaderPageActivity")
READING_MINUTES = 11.0
READING_INTERVAL = 30.0


def _foreground_activity() -> str:
    try:
        out = subprocess.run(
            [str(ADB), "-s", DEVICE, "shell", "dumpsys", "window"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True,
            timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout.decode("utf-8", errors="replace")
        for line in out.splitlines():
            if "mCurrentFocus" in line:
                return line
    except Exception:
        pass
    return ""


def _kill_python_tree(pid: int) -> None:
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       check=False, timeout=10,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        pass


def _back_to_qqreader_main(attempts: int = 4) -> None:
    """Press BACK until we are back on the QQ Reader main UI (screenshot-able).
    Maa needs a normal page to find the book; any leftover webview / ad page
    will make ReadingFindBook fail."""
    for _ in range(attempts):
        line = _foreground_activity()
        if "MainFlutterActivity" in line:
            return
        if "com.qq.reader" not in line:
            try:
                subprocess.run(
                    [str(ADB), "-s", DEVICE, "shell", "input", "keyevent", "4"],
                    check=False, timeout=10,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except Exception:
                pass
            time.sleep(1.5)
        else:
            # Still inside QQ Reader but on some webview/reader page.
            try:
                subprocess.run(
                    [str(ADB), "-s", DEVICE, "shell", "input", "keyevent", "4"],
                    check=False, timeout=10,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except Exception:
                pass
            time.sleep(1.5)


def run_reading_task(entry: str) -> int:
    """DailyReadingFlow special handling.

    The QQ Reader reader page forbids ADB screencap, so Maa can open the book
    but then freezes (every pipeline node tries to screencap and fails).  The
    reading task only needs ~10 minutes of page-turning, which this function
    drives directly:

      1. Make sure we are back on the QQ Reader main UI (screenshot-able).
      2. Launch Maa on DailyReadingFlow so it finds and opens the book.
      3. Poll the foreground activity until the reader page appears.
      4. Kill Maa (it is useless on the non-screenshotable reader page).
      5. Run reading_watch.py to turn pages for 11 minutes.
      6. Relaunch the supervised ClaimOneReward to claim the reward.
    """
    _back_to_qqreader_main()
    for attempt in range(1, 4):
        print(f"[{datetime.now():%H:%M:%S}] reading task: launching Maa to "
              f"open the book (attempt {attempt}/3)", flush=True)
        process = subprocess.Popen(
            [sys.executable, str(RUNNER), entry, "--device", DEVICE],
            cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
            env=os.environ.copy(),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        reader_seen = False
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if "ReaderPageActivity" in _foreground_activity():
                reader_seen = True
                break
            if process.poll() is not None:
                break
            time.sleep(1.0)
        if reader_seen:
            break
        print(f"[{datetime.now():%H:%M:%S}] reading task: reader page never "
              f"appeared (Maa exit {process.returncode}); back to main and retry",
              flush=True)
        _kill_python_tree(process.pid)
        _back_to_qqreader_main()
        time.sleep(2.0)
    if not reader_seen:
        print(f"[{datetime.now():%H:%M:%S}] reading task: could not open the "
              f"book after 3 attempts", flush=True)
        return 2

    print(f"[{datetime.now():%H:%M:%S}] reading task: reader page active; "
          f"stopping Maa and starting page-turn watch", flush=True)
    _kill_python_tree(process.pid)
    result = subprocess.run(
        [str(PYTHON), str(READING_WATCH), "--adb", str(ADB), "--device", DEVICE,
         "--minutes", str(READING_MINUTES), "--interval", str(READING_INTERVAL)],
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", timeout=60 * 60,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    print(f"[{datetime.now():%H:%M:%S}] reading watch done: "
          f"{result.stdout.strip()[-200:]}", flush=True)

    # Back on the (screenshot-able) main UI — claim the reading reward now,
    # under the full supervisor (so CAPTCHAs / ad pages are still handled).
    print(f"[{datetime.now():%H:%M:%S}] reading task: claiming reward via "
          f"supervised ClaimOneReward", flush=True)
    return supervise_entry("ClaimOneReward")


def supervise_entry(entry: str, max_restarts: int = 2,
                    deadline_seconds: float = 3 * 60 * 60) -> int:
    """Run one Maa pipeline entry under the supervisor loop (CAPTCHA / ad
    locator / ad-close handling + ad-stall restart).  Shared by the plain
    entry path and the reading task's claim phase."""
    captcha_seen_at = 0.0
    slide_seen_at = 0.0
    slide_attempts = 0
    slide_max_attempts = 6
    post_ad_seen_at = 0.0
    shelf_nav_seen_at = 0.0
    ad_locator_seen_at = 0.0
    ad_locator_attempts = 0
    # Keep the ad-locator disabled: it can mis-read the "邀请" button on the
    # reward page and navigate away from the ad flow.  Maa's own pipeline is
    # responsible for finding/clicking the watch button.
    ad_locator_max_attempts = 0
    ad_close_seen_at = 0.0
    webview_seen_at = 0.0
    webview_forced = False
    pending_text = ""
    deadline = time.monotonic() + deadline_seconds
    restart_count = 0

    while restart_count <= max_restarts and time.monotonic() < deadline:
        if LOG.exists():
            offset = LOG.stat().st_size
        else:
            offset = 0
        process = subprocess.Popen(
            [sys.executable, str(RUNNER), entry, "--device", DEVICE],
            cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
            env=os.environ.copy(),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        print(f"[{datetime.now():%H:%M:%S}] started Maa supervisor for {entry} "
              f"(pid={process.pid}, restart={restart_count})", flush=True)
        ad_close_stuck = False
        while process.poll() is None and time.monotonic() < deadline:
            if LOG.exists():
                current_size = LOG.stat().st_size
                # Maa may rotate or truncate maafw.log when a new run starts.  If the
                # stored offset now points past the current end of the file we are
                # reading from a stale position and would silently miss every event
                # for the rest of the run, which is exactly the bug that caused the
                # v1 supervisor to log nothing.  Snap forward to the live size.
                if offset > current_size:
                    offset = 0
                with LOG.open("rb") as stream:
                    stream.seek(offset)
                    chunk = stream.read()
                    offset = stream.tell()
                text = chunk.decode("utf-8", errors="replace") if chunk else ""
            else:
                text = ""
            if text:
                pending_text = (pending_text + text)[-20000:]
                if "Tasker.Task.Succeeded" in pending_text:
                    print(f"[{datetime.now():%H:%M:%S}] Maa task succeeded", flush=True)
                    pending_text = pending_text.replace("Tasker.Task.Succeeded", "Tasker.Task.Succeeded[reported]")
                if "Tasker.Task.Failed" in pending_text:
                    print(f"[{datetime.now():%H:%M:%S}] Maa task reported failure", flush=True)
                    pending_text = pending_text.replace("Tasker.Task.Failed", "Tasker.Task.Failed[reported]")
                if (
                    captcha_signal(text)
                    and time.monotonic() - captcha_seen_at > 8
                ):
                    captcha_seen_at = time.monotonic()
                    print(f"[{datetime.now():%H:%M:%S}] detected CAPTCHA; solving from fresh screenshots", flush=True)
                    if not solve_captcha():
                        print(f"[{datetime.now():%H:%M:%S}] CAPTCHA was not confirmed; leaving Maa paused", flush=True)
                        return 2
                    print(f"[{datetime.now():%H:%M:%S}] CAPTCHA submitted; Maa will resume", flush=True)
                if (
                    ("安全验证" in text or "screencap failed" in text or ad_not_found_signal(text))
                    and time.monotonic() - slide_seen_at > 8
                    and slide_attempts < slide_max_attempts
                ):
                    slide_seen_at = time.monotonic()
                    slide_attempts += 1
                    print(f"[{datetime.now():%H:%M:%S}] checking slide CAPTCHA "
                          f"(attempt {slide_attempts}/{slide_max_attempts})", flush=True)
                    if any(k in text for k in ("安全验证", "拖动", "向右滑动")):
                        capture_slide_evidence()
                    if solve_slide_captcha():
                        print(f"[{datetime.now():%H:%M:%S}] slide CAPTCHA solved", flush=True)
                    else:
                        print(f"[{datetime.now():%H:%M:%S}] no slide CAPTCHA detected", flush=True)
                if (
                    ad_not_found_signal(text)
                    and time.monotonic() - ad_locator_seen_at > 6
                    and ad_locator_attempts < ad_locator_max_attempts
                ):
                    ad_locator_seen_at = time.monotonic()
                    ad_locator_attempts += 1
                    print(f"[{datetime.now():%H:%M:%S}] ad entry not found; "
                          f"locating ad div (attempt {ad_locator_attempts}/{ad_locator_max_attempts})", flush=True)
                    if locate_ad():
                        print(f"[{datetime.now():%H:%M:%S}] ad div located and watch button clicked", flush=True)
                    else:
                        print(f"[{datetime.now():%H:%M:%S}] ad div locate/click did not confirm", flush=True)
                if (
                    _POST_AD_RE.search(text)
                    and time.monotonic() - post_ad_seen_at > POST_AD_CHECK_INTERVAL
                ):
                    post_ad_seen_at = time.monotonic()
                    print(f"[{datetime.now():%H:%M:%S}] ad-end signal seen; "
                          f"running post-ad CAPTCHA classification", flush=True)
                    check_post_ad_captcha()
                # NOTE: deliberately do NOT force-close or send Back on ad pages.
                # The user wants to stay on the ad page and let Maa finish it.
            time.sleep(0.5)
        if process.poll() is None:
            process.terminate()
            return 3
        print(f"[{datetime.now():%H:%M:%S}] Maa exited with code {process.returncode}", flush=True)
        return int(process.returncode or 0)
    print(f"[{datetime.now():%H:%M:%S}] gave up after {max_restarts} ad-close restarts", flush=True)
    return 4


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    global DEVICE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--device", default=DEVICE,
        help="MuMu ADB device serial the QQ Reader instance listens on "
             "(default %(default)s; on this machine QQ Reader is on 127.0.0.1:16385)",
    )
    parser.add_argument(
        "--entry", default="DailyAdFlow",
        help="Maa pipeline entry node to run (default %(default)s)",
    )
    args = parser.parse_args()
    DEVICE = args.device
    # MuMu uses its own ADB server on 5038; without this the direct MaaFramework
    # runner and the local clicker talk to the right server.
    os.environ["ANDROID_ADB_SERVER_PORT"] = "5038"
    if not RUNNER.exists():
        raise SystemExit(f"Maa task runner not found: {RUNNER}")
    if args.entry == "DailyReadingFlow":
        return run_reading_task(args.entry)
    return supervise_entry(args.entry)


if __name__ == "__main__":
    raise SystemExit(main())
