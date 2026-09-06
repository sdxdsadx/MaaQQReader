"""Locate and tap the close (X) button on QQ Reader's ad pages.

The full-screen ads shown by QQ Reader are powered by the Pangle (穿山甲)
SDK (``com.bytedance.sdk.openadsdk.stub.activity.Stub_Standard_Portrait_Activity``).
Those pages are video/image only — they contain **no OCR-able text**, so the
Maa pipeline's OCR-based close nodes (``AdClosableAfterCountdown`` etc.) can
never "see" the X icon and the flow stalls after the 35s countdown.

This helper finds the close button the way a human would: by looking at the
pixels.  It tries, in order:

1. **Template match** against a small set of built-in white "X" glyphs in the
   top band (the Pangle X is a white cross, ~20-40px, top-left or top-right).
2. **Shape analysis** — white connected blobs in the top band whose skeleton
   looks like two crossing diagonal strokes (an "X"), scored and ranked.
3. **Fixed positions** — Pangle's X sits at a stable spot: top-left around
   (52, 112) or top-right around (670, 112).  Tap those in order.

After a tap it re-screenshots and, if the ad activity is still in the
foreground, reports ``still_visible: true`` so the caller can escalate to the
BACK key (or give up).

CLI (mirrors the other tools):

    python ad_close_finder.py --adb <adb.exe> --device 127.0.0.1:16385 \
        [--click] [--back-if-fail] [--output <png>]

It prints one JSON line::

    {"found": true, "method": "template", "x": 57, "y": 119,
     "clicked": true, "still_visible": false, "activity": "..."}
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np


# The Pangle ad X button typically lives at these fixed spots when nothing
# else matched.  Verified by Codex judgement on real screenshots: top-left
# X at ~(57,119) on the search-page ad, ~(56,117) on the live-room ad.
FIXED_CANDIDATES = [(52, 112), (670, 112), (57, 119), (668, 118)]

# Top band we search for the X in (the ad UI bar).
SEARCH_BAND = (0, 60, 720, 300)

AD_ACTIVITY_RE = re.compile(r"openadsdk|Pangle|bytedance", re.IGNORECASE)


def adb_bytes(adb: Path, device: str, *args: str) -> bytes:
    completed = subprocess.run(
        [str(adb), "-s", device, *args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return completed.stdout


def screenshot(adb: Path, device: str) -> tuple[bytes, np.ndarray]:
    data = adb_bytes(adb, device, "exec-out", "screencap", "-p")
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError("ADB screenshot could not be decoded")
    return data, image


def foreground_activity(adb: Path, device: str) -> str:
    try:
        out = adb_bytes(adb, device, "shell", "dumpsys", "window").decode(
            "utf-8", errors="replace")
        for line in out.splitlines():
            if "mCurrentFocus" in line:
                return line.strip()
    except Exception:
        pass
    return ""


def is_ad_foreground(adb: Path, device: str) -> bool:
    return bool(AD_ACTIVITY_RE.search(foreground_activity(adb, device)))


# --- X glyph templates -----------------------------------------------------

def _make_x_templates() -> list[np.ndarray]:
    """Small white X glyphs at different line weights, as match templates.

    The real Pangle X is ~22-26 px with a ~2-3 px stroke, drawn dark-on-light
    (or light-on-dark depending on the ad).  Templates that are too big
    dilute the correlation score, so we keep them close to the real size.
    """
    templates: list[np.ndarray] = []
    for size in (22, 24, 26, 28, 30):
        for stroke in (2, 3, 4):
            t = np.zeros((size + 8, size + 8), np.uint8)
            c = size // 2 + 4
            for d in range(-size // 2, size // 2 + 1):
                cv2.line(t, (c + d, c + d), (c + d + stroke - 1, c + d + stroke - 1), 255, 1)
                cv2.line(t, (c - d, c + d), (c - d - stroke + 1, c + d + stroke - 1), 255, 1)
            templates.append(t)
    return templates


X_TEMPLATES = _make_x_templates()
TEMPLATE_THRESHOLD = 0.42


def _locate_by_template(gray: np.ndarray) -> tuple[int, int] | None:
    """Match built-in X glyphs in the top band; return best center.

    Runs against both the natural image and its inverse, because the Pangle
    X can be either a dark glyph on light background (real capture at
    (57,119): value ~25 on ~246) or a white glyph on a dark scrim.  The best
    of the two polarities wins.
    """
    band = gray[SEARCH_BAND[1]:SEARCH_BAND[3], SEARCH_BAND[0]:SEARCH_BAND[2]]
    best: tuple[float, int, int, int, int] | None = None
    for image_band in (band, 255 - band):
        for t in X_TEMPLATES:
            th, tw = t.shape
            if th >= image_band.shape[0] or tw >= image_band.shape[1]:
                continue
            res = cv2.matchTemplate(image_band, t, cv2.TM_CCOEFF_NORMED)
            _, maxv, _, maxloc = cv2.minMaxLoc(res)
            if best is None or maxv > best[0]:
                best = (float(maxv), int(maxloc[0]), int(maxloc[1]), tw, th)
    if best is None or best[0] < TEMPLATE_THRESHOLD:
        return None
    _, bx, by, tw, th = best
    return (SEARCH_BAND[0] + bx + tw // 2, SEARCH_BAND[1] + by + th // 2)


def _locate_by_shape(gray: np.ndarray) -> tuple[int, int] | None:
    """White/dark blobs in the top band ranked by how X-like they are.

    The Pangle X is drawn in *either* polarity: white glyph on dark scrim, or
    dark glyph on light background (real capture: a ~22x24 px glyph with
    pixel value ~25 on a ~246 background at (57,119)).  So we score both a
    dark mask and a bright mask and keep the best X-like blob overall.
    """
    band = gray[SEARCH_BAND[1]:SEARCH_BAND[3], SEARCH_BAND[0]:SEARCH_BAND[2]]
    masks = {}
    _, masks["bright"] = cv2.threshold(band, 200, 255, cv2.THRESH_BINARY)
    _, masks["dark"] = cv2.threshold(band, 90, 255, cv2.THRESH_BINARY_INV)
    scored: list[tuple[float, int, int, int, int, str]] = []
    for name, mask in masks.items():
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        n, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        for i in range(1, n):
            x, y, bw, bh, area = map(int, stats[i])
            if not (8 <= bw <= 70 and 8 <= bh <= 70 and area >= 35):
                continue
            # X-shape score: glyph pixels should concentrate along both
            # diagonals (the crossing strokes of an X).
            patch = mask[y:y + bh, x:x + bw]
            side = min(bw, bh)
            diag1 = sum(int(patch[i, i]) > 0 for i in range(side))
            diag2 = sum(int(patch[i, side - 1 - i]) > 0 for i in range(side))
            # Compactness bonus: an X is thin, so its area is a small
            # fraction of the bounding box.
            npx = int(np.count_nonzero(patch))
            fill = npx / max(1, bw * bh)
            score = (diag1 + diag2) * 2.0 / max(1, npx)
            if fill > 0.75:
                score *= 0.5  # solid square/rectangle, not an X
            scored.append((score, x, y, bw, bh, name))
    if not scored:
        return None
    scored.sort(reverse=True)
    score, x, y, bw, bh, name = scored[0]
    if score < 1.15:
        return None
    return (SEARCH_BAND[0] + x + bw // 2, SEARCH_BAND[1] + y + bh // 2)


def tap(adb: Path, device: str, x: int, y: int, settle: float = 0.8) -> bool:
    try:
        adb_bytes(adb, device, "shell", "input", "tap", str(int(x)), str(int(y)))
        time.sleep(settle)
        return True
    except Exception:
        return False


def press_back(adb: Path, device: str, settle: float = 1.0) -> bool:
    try:
        adb_bytes(adb, device, "shell", "input", "keyevent", "4")
        time.sleep(settle)
        return True
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", type=Path, required=True)
    parser.add_argument("--device", default="127.0.0.1:16385")
    parser.add_argument("--image", type=Path, help="local screenshot instead of adb")
    parser.add_argument("--click", action="store_true", help="tap the located X")
    parser.add_argument("--back-if-fail", action="store_true",
                        help="press BACK when no X found (and still on an ad page)")
    parser.add_argument("--output", type=Path, help="save annotated screenshot")
    args = parser.parse_args()

    if args.image:
        image_bytes = args.image.read_bytes()
        image = cv2.imread(str(args.image))
    else:
        image_bytes, image = screenshot(args.adb, args.device)
    if image is None:
        print(json.dumps({"found": False, "error": "cannot read image"}))
        return 1
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    method = "none"
    point = _locate_by_template(gray)
    if point is not None:
        method = "template"
    else:
        point = _locate_by_shape(gray)
        if point is not None:
            method = "shape"
    if point is None:
        # Fixed-position fallback.
        for fx, fy in FIXED_CANDIDATES:
            if is_ad_foreground(args.adb, args.device) or args.image is not None:
                point = (fx, fy)
                method = f"fixed({fx},{fy})"
                break
    if point is None:
        point = FIXED_CANDIDATES[0]
        method = "fixed(52,112)"

    found = point is not None
    clicked = False
    if args.click and found:
        clicked = tap(args.adb, args.device, *point)
    still_visible = False
    if args.click and not args.image:
        time.sleep(1.0)
        still_visible = is_ad_foreground(args.adb, args.device)
    if args.click and not clicked and not args.image:
        still_visible = is_ad_foreground(args.adb, args.device)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        marked = image.copy()
        if found:
            cv2.circle(marked, point, 22, (0, 0, 255), 3)
            cv2.putText(marked, method, (max(0, point[0] - 40), max(30, point[1] - 30)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        cv2.imwrite(str(args.output), marked)

    payload: dict[str, object] = {
        "found": found,
        "method": method,
        "x": int(point[0]) if point else None,
        "y": int(point[1]) if point else None,
        "clicked": clicked,
        "still_visible": still_visible,
    }
    if not args.image:
        payload["activity"] = foreground_activity(args.adb, args.device)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
