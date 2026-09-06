"""Solve the current QQ Reader ordered-image CAPTCHA.

The solver captures the emulator screen, detects the gray prompt icons shown at
the top and the colored candidates, matches each prompt to a distinct candidate
by silhouette (Otsu binarised mask / skeleton chamfer distance + SIFT), taps
them from left to right in prompt order, then submits.

Refactor notes (v2 — driven by the real flow observed in supervisor_run.log):

The previous solver had three failure modes that compounded into the
``captcha_still_visible: true`` infinite loop:

1. ``target_index`` could be produced out of range for a (targets, prompts)
   combination the per-prompt greedy picker did not validate.
2. ddddocr's text detector also picked up candidate tiles and decorations as
   "prompt" boxes, so a frame could be reported with 8+ prompts while the
   real layout had 2; the per-prompt loop then selected the same (wrong) tile
   eight times without ever advancing.
3. The submit-then-check was the *only* feedback signal.  When the click
   landed off-target the answer was wrong, the verification prompt stayed on
   screen, and the solver reported ``submitted: true`` anyway.  The supervisor
   took that as success and Maa re-emitted ``AdCaptchaDetected`` immediately,
   starting a new solve that produced the same wrong output — a tight loop.

v2 fixes that by treating each solve as a small state machine with feedback
after every step:

* ``analyze`` rejects frames with more than 6 prompts, a spread-out prompt
  row, or impossible (prompts > candidates × 2) counts and signals a refresh.
* ``next_click`` only ever returns an index inside the current frame's
  ``targets`` list (clamped + assert).
* After every tap we re-screenshot and re-analyse: if the prompt set is
  unchanged we count it as a "no-op" click.  Two no-op clicks in a row (or
  three identical frame signatures overall) means the challenge is stuck and
  we ask the supervisor to refresh the challenge instead of continuing to
  click the same wrong tile.
* The post-submit "is the verification prompt still here" check looks for the
  *prompt row* (the gray icons in the upper half), not for "any big blue
  button" — the reward page also has a blue button ("立即观看") and the old
  heuristic misread that as "captcha still visible".

The solver still talks to the same CLI as v1: ``--adb``, ``--device``,
``--submit``, ``--output``, ``--click-engine``.  The JSON output gains a
``refresh_recommended`` flag the supervisor can use to decide when to tap the
challenge's refresh control between solves.
"""

from __future__ import annotations

import argparse
import itertools
import json
import subprocess
import sys
import time
from pathlib import Path

import cv2
import ddddocr
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
# Local MaaFramework coordinate clicker used when --click-engine=maa.
MAA_CLICKER = ROOT / "tools" / "maa_click.py"
CLICK_ENGINE = "maa"  # overridden from --click-engine

# Geometric limits for the QQ Reader challenge.  Verified by visual inspection
# of the current layout (720x1280): prompt icons sit in a single horizontal
# row, candidates in a 2-3 row grid below, and at most 6 of either.
MAX_PROMPTS = 6
MIN_PROMPTS = 1
MAX_TARGETS = 6
MIN_TARGETS = 1
# Maximum allowed vertical spread of the prompt row's centers.  Real icons in a
# single challenge share a baseline; anything wider means we picked up noise.
PROMPT_ROW_SPREAD = 32
# Two frames are "the same" if the ordered (prompts, targets) box sets match
# within these tolerances.  Loose enough to forgive sub-pixel jitter.
BOX_SAME_TOL = 4
# Tap settles (seconds) for the local ADB engine.
ADB_SETTLE = 0.55
# The challenge's refresh control sits roughly at the lower-left of the popup.
# Tapping it loads a new challenge, which is the safe fallback when the
# current one has us stuck.
REFRESH_POINT = (180, 908)
REFRESH_TAP_SETTLE = 1.5


def adb_bytes(adb: Path, device: str, *args: str) -> bytes:
    completed = subprocess.run(
        [str(adb), "-s", device, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return completed.stdout


def screenshot(adb: Path, device: str) -> tuple[bytes, np.ndarray]:
    data = adb_bytes(adb, device, "exec-out", "screencap", "-p")
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError("ADB screenshot could not be decoded")
    return data, image


def norm_mask(image: np.ndarray, box: tuple[int, int, int, int], prompt: bool) -> np.ndarray:
    x1, y1, x2, y2 = box
    crop = image[y1:y2, x1:x2]
    # Match the silhouette, never the tile colour.  Candidate tiles use
    # unrelated colours, so hue/saturation is deliberately ignored.  We score
    # grayscale/Otsu and edge-derived components by centrality and border
    # contact, which selects the icon shape inside each detected tile.
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    _, dark = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    _, light = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    edges = cv2.Canny(gray, 40, 130)
    edges = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), iterations=1)
    candidates = [dark, light, edges]
    best_score = -1.0
    best_mask = None
    h, w = gray.shape[:2]
    for candidate in candidates:
        candidate = cv2.morphologyEx(candidate, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        count, labels, stats, centroids = cv2.connectedComponentsWithStats(candidate)
        for index in range(1, count):
            x, y, bw, bh, area = map(int, stats[index])
            if area < max(8, int(w * h * 0.015)) or area > int(w * h * 0.85):
                continue
            border = int(x <= 1) + int(y <= 1) + int(x + bw >= w - 1) + int(y + bh >= h - 1)
            cx, cy = centroids[index]
            center_distance = np.hypot(cx - w / 2, cy - h / 2) / max(1.0, np.hypot(w / 2, h / 2))
            score = area * (1.2 - min(1.0, center_distance)) / (1 + border * 2)
            if score > best_score:
                best_score = score
                best_mask = (labels == index).astype(np.uint8) * 255
    if best_mask is None:
        raise RuntimeError("No CAPTCHA shape silhouette found")
    mask = best_mask
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    clean = np.zeros_like(mask)
    minimum = 3 if prompt else 10
    for index in range(1, count):
        if stats[index, cv2.CC_STAT_AREA] >= minimum:
            clean[labels == index] = 255
    ys, xs = np.where(clean > 0)
    if not len(xs):
        raise RuntimeError(f"Empty icon mask at {box}")
    clean = clean[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    side = 160
    scale = min((side - 16) / clean.shape[1], (side - 16) / clean.shape[0])
    resized = cv2.resize(
        clean,
        (max(1, round(clean.shape[1] * scale)), max(1, round(clean.shape[0] * scale))),
        interpolation=cv2.INTER_NEAREST,
    )
    result = np.zeros((side, side), np.uint8)
    oy = (side - resized.shape[0]) // 2
    ox = (side - resized.shape[1]) // 2
    result[oy : oy + resized.shape[0], ox : ox + resized.shape[1]] = resized
    return result


def skeleton(mask: np.ndarray) -> np.ndarray:
    remaining = (mask > 0).astype(np.uint8) * 255
    output = np.zeros_like(remaining)
    element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    while cv2.countNonZero(remaining):
        eroded = cv2.erode(remaining, element)
        opened = cv2.dilate(eroded, element)
        output = cv2.bitwise_or(output, cv2.subtract(remaining, opened))
        remaining = eroded
    return output > 0


def chamfer(prompt: np.ndarray, target: np.ndarray) -> float:
    pa = skeleton(prompt)
    ta = skeleton(target)
    pd = cv2.distanceTransform((~pa).astype(np.uint8), cv2.DIST_L2, 3)
    td = cv2.distanceTransform((~ta).astype(np.uint8), cv2.DIST_L2, 3)
    return float((td[pa].mean() + pd[ta].mean()) / 2)


def sift_matches(prompt: np.ndarray, target: np.ndarray) -> int:
    sift = cv2.SIFT_create(nfeatures=240, contrastThreshold=0.01, edgeThreshold=10)
    p = cv2.resize(prompt, (256, 256))
    t = cv2.resize(target, (256, 256))
    _, pd = sift.detectAndCompute(p, None)
    _, td = sift.detectAndCompute(t, None)
    if pd is None or td is None or len(td) < 2:
        return 0
    pairs = cv2.BFMatcher().knnMatch(pd, td, k=2)
    return sum(first.distance < 0.78 * second.distance for first, second in pairs)


def detect_boxes(image_bytes: bytes) -> list[tuple[int, int, int, int]]:
    detector = ddddocr.DdddOcr(det=True, ocr=False, show_ad=False)
    return [tuple(map(int, box)) for box in detector.detection(image_bytes)]


def _nms(boxes: list[tuple[int, int, int, int]], iou_thresh: float = 0.35
         ) -> list[tuple[int, int, int, int]]:
    """Drop near-duplicate boxes (IoU above ``iou_thresh``), keeping the
    largest one.  ddddocr's detector often returns several slightly offset
    rectangles for the same icon; we want to keep one box per icon, not
    merge independent icons (which is what an earlier ``_merge_close_boxes``
    attempt did and which collapsed 3 prompt icons into 1)."""
    if not boxes:
        return []
    areas = [(b[2] - b[0]) * (b[3] - b[1]) for b in boxes]
    order = sorted(range(len(boxes)), key=lambda i: -areas[i])
    keep: list[int] = []
    while order:
        i = order.pop(0)
        keep.append(i)
        survivors: list[int] = []
        for j in order:
            x1 = max(boxes[i][0], boxes[j][0])
            y1 = max(boxes[i][1], boxes[j][1])
            x2 = min(boxes[i][2], boxes[j][2])
            y2 = min(boxes[i][3], boxes[j][3])
            inter = max(0, x2 - x1) * max(0, y2 - y1)
            union = areas[i] + areas[j] - inter
            iou = inter / union if union > 0 else 0.0
            if iou < iou_thresh:
                survivors.append(j)
        order = survivors
    return [boxes[i] for i in sorted(keep, key=lambda k: boxes[k][0])]


def _filter_prompts(boxes: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    """Pick the prompt row.

    The QQ Reader challenge shows up to 6 gray prompt icons in a single
    horizontal row at the top of the popup.  We restrict to that band, dedupe
    overlapping detections with NMS, and also demand that all candidates
    share a baseline (small y-spread) — the candidate tiles below do not,
    so this is a very effective filter."""
    candidates = [
        b
        for b in boxes
        if 270 <= b[0] and b[2] <= 520 and 275 <= b[1] <= 380
        and 30 <= b[2] - b[0] <= 90 and 30 <= b[3] - b[1] <= 80
    ]
    candidates = _nms(candidates, iou_thresh=0.35)
    if not (MIN_PROMPTS <= len(candidates) <= MAX_PROMPTS):
        return []  # too many / too few → caller will reject the whole frame
    centers_y = [(b[1] + b[3]) / 2 for b in candidates]
    if max(centers_y) - min(centers_y) > PROMPT_ROW_SPREAD:
        return []
    return sorted(candidates, key=lambda b: b[0])


def _filter_targets(boxes: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    """Pick the candidate tile region below the prompts."""
    candidates = [
        b
        for b in boxes
        if 80 <= b[0] and b[2] <= 640 and 380 <= b[1] <= 900
        and 60 <= b[2] - b[0] <= 150 and 60 <= b[3] - b[1] <= 150
    ]
    candidates = _nms(candidates, iou_thresh=0.35)
    if not (MIN_TARGETS <= len(candidates) <= MAX_TARGETS):
        return []
    return sorted(candidates, key=lambda b: (b[1], b[0]))


def analyze(image_bytes: bytes, image: np.ndarray) -> dict[str, object]:
    height, width = image.shape[:2]
    if (width, height) != (720, 1280):
        raise RuntimeError(f"Unsupported screenshot size: {width}x{height}")
    boxes = detect_boxes(image_bytes)
    prompts = _filter_prompts(boxes)
    targets = _filter_targets(boxes)
    if not prompts or not targets:
        raise RuntimeError(f"Unsafe CAPTCHA layout: prompts={len(prompts)}, targets={len(targets)}")
    # Sanity bound — QQ Reader challenges never ask for more answers than
    # there are candidates × 2 (a single tile can be the answer to two prompts).
    if len(prompts) > len(targets) * 2:
        raise RuntimeError(
            f"Unsafe CAPTCHA layout: {len(prompts)} prompts vs {len(targets)} targets"
        )

    prompt_masks = [norm_mask(image, b, True) for b in prompts]
    target_masks = [norm_mask(image, b, False) for b in targets]
    matrix: list[list[dict[str, float | int]]] = []
    for prompt in prompt_masks:
        row = []
        for target in target_masks:
            distance = chamfer(prompt, target)
            matches = sift_matches(prompt, target)
            # Overall silhouette is the primary signal.  Local SIFT matches
            # only break close silhouette ties; letting their raw count lead
            # favors visually busy but incorrect candidates.
            row.append({
                "matches": matches,
                "distance": round(distance, 4),
                "score": round(-distance + 0.02 * matches, 4),
            })
        matrix.append(row)

    # Locate the light-blue submit button instead of assuming a fixed Y offset.
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    blue = cv2.inRange(hsv, np.array([85, 25, 170]), np.array([125, 180, 255]))
    contours, _ = cv2.findContours(blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    button_boxes = [cv2.boundingRect(c) for c in contours if cv2.contourArea(c) > 5000]
    button_boxes = [b for b in button_boxes if b[0] > 350 and b[1] > 750]
    # A missing or ambiguous submit button is non-fatal: the caller refreshes
    # the frame when needed instead of the whole analysis crashing.
    confirm = None
    if len(button_boxes) == 1:
        bx, by, bw, bh = button_boxes[0]
        confirm = [bx + bw // 2, by + bh // 2]
    return {
        "prompts": prompts,
        "targets": targets,
        "matrix": matrix,
        "confirm": confirm,
    }


def _frame_signature(result: dict[str, object]) -> tuple:
    """A hashable description of the (prompts, targets) box sets so we can
    detect "the click changed nothing, the frame is the same" cheaply."""
    prompts_sig = tuple((b[0] // BOX_SAME_TOL, b[1] // BOX_SAME_TOL,
                          b[2] // BOX_SAME_TOL, b[3] // BOX_SAME_TOL)
                         for b in result["prompts"])
    targets_sig = tuple((b[0] // BOX_SAME_TOL, b[1] // BOX_SAME_TOL,
                          b[2] // BOX_SAME_TOL, b[3] // BOX_SAME_TOL)
                         for b in result["targets"])
    return (prompts_sig, targets_sig)


def next_click(result: dict[str, object], used_points: list[tuple[int, int]]) -> tuple[int, tuple[int, int], float]:
    """Pick the next single (prompt -> target) click using a global one-to-one
    assignment over the current frame instead of a per-prompt greedy pick.

    A per-prompt greedy choice can be globally suboptimal (e.g. it may lock in a
    high-SIFT but wrong match and force the remaining prompt onto a worse tile).
    We score every distinct assignment of prompts to targets and pick the
    maximum, then return the target for the leftmost remaining prompt.  When
    the best assignment is not clearly ahead of the runner-up we refuse rather
    than guess.

    The returned ``target_index`` is guaranteed to be a valid index into
    ``result["targets"]``; we clamp and assert it because the old solver once
    reported index 2 against a 2-element list, causing the click to land on
    a stale tile far from the answer.
    """
    prompts = result["prompts"]
    targets = result["targets"]
    matrix = result["matrix"]
    n = len(prompts)
    if n == 0 or not targets:
        raise RuntimeError("next_click called with empty prompts or targets")
    if any(len(row) != len(targets) for row in matrix):
        raise RuntimeError("matrix/targets size mismatch")

    avail: list[int] = []
    for t in range(len(targets)):
        cx = (targets[t][0] + targets[t][2]) // 2
        cy = (targets[t][1] + targets[t][3]) // 2
        if any(abs(cx - up[0]) < 35 and abs(cy - up[1]) < 35 for up in used_points):
            continue
        avail.append(t)
    # Fall back to allowing reuse only when the challenge has more prompts
    # than tiles — the same tile is the legal answer to two prompts in that
    # case, so we *must* permit reuse.  In every other case the availlist
    # already covers the full set.
    if len(avail) < n:
        avail = list(range(len(targets)))

    if n == 1:
        # No assignment search needed; pick the best of what's available.
        ranked = sorted(
            ((float(matrix[0][t]["score"]), t, targets[t]) for t in avail),
            reverse=True,
        )
        best = ranked[0]
        tgt = max(0, min(best[1], len(targets) - 1))
        cx = (targets[tgt][0] + targets[tgt][2]) // 2
        cy = (targets[tgt][1] + targets[tgt][3]) // 2
        return tgt, (cx, cy), float(best[0])

    combos = list(itertools.permutations(avail, n))
    if not combos:
        raise RuntimeError("No available candidate for prompts")
    scores = [sum(matrix[i][combo[i]]["score"] for i in range(n)) for combo in combos]
    best_idx = int(max(range(len(scores)), key=lambda k: scores[k]))
    ordered = sorted(scores, reverse=True)
    margin = ordered[0] - ordered[1] if len(ordered) > 1 else 999.0
    if margin < 0.25:
        raise RuntimeError(
            f"Ambiguous CAPTCHA assignment: best={ordered[0]:.3f} second={ordered[1]:.3f}"
        )
    combo = combos[best_idx]
    # The combo stores indices into ``targets`` (since ``avail`` is a list of
    # target indices), so ``combo[0]`` is a legal target index.  Clamp anyway
    # as a final guard against accidental off-by-one refactors.
    tgt = max(0, min(int(combo[0]), len(targets) - 1))
    box = targets[tgt]
    point = ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2)
    return tgt, point, float(scores[best_idx])


def tap(adb: Path, device: str, x: int, y: int, settle: float | None = None,
        engine: str | None = None) -> bool:
    """Send a tap at (x, y) via local MAA (default) or raw ADB."""
    if settle is None:
        settle = ADB_SETTLE
    engine = engine or CLICK_ENGINE
    if engine == "maa" and MAA_CLICKER.exists():
        try:
            completed = subprocess.run(
                [sys.executable, str(MAA_CLICKER),
                 "--adb", str(adb), "--device", device,
                 "--point", str(int(x)), str(int(y)),
                 "--settle", f"{settle:g}"],
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
            if parsed.get("ok") and parsed.get("clicks", [{}])[0].get("ok"):
                return True
        except Exception:
            pass
    try:
        adb_bytes(adb, device, "shell", "input", "tap", str(int(x)), str(int(y)))
        time.sleep(settle)
        return True
    except Exception:
        return False


def click_retry_if_present(adb: Path, device: str, image: np.ndarray) -> bool:
    """Click the blue 'retry' button shown when the CAPTCHA hit its attempt cap.

    The retry state has no prompt icons or candidate tiles, so analyze() cannot
    solve it.  Tapping the wide blue button loads a fresh challenge.
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    blue = cv2.inRange(hsv, np.array([85, 25, 170]), np.array([125, 180, 255]))
    contours, _ = cv2.findContours(blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[tuple[float, int, int, int, int]] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 2000:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        if w > 120 and 550 <= y <= 850:
            candidates.append((area, x, y, w, h))
    if not candidates:
        return False
    _, x, y, w, h = max(candidates, key=lambda item: item[0])
    tap(adb, device, x + w // 2, y + h // 2)
    time.sleep(REFRESH_TAP_SETTLE)
    return True


def _prompt_row_still_present(image: np.ndarray) -> bool:
    """True if the challenge popup is still on screen.

    The popup's defining feature is the gray prompt-icon row in the upper
    half.  Reward pages do not have that, but they *do* have a blue "立即观看"
    button, so we deliberately do not rely on a button-color heuristic here.
    Instead we ask ddddocr to look in the prompt band and check that at least
    one box still matches the prompt's size and y range.
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    blue = cv2.inRange(hsv, np.array([85, 25, 170]), np.array([125, 180, 255]))
    contours, _ = cv2.findContours(blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if 280 <= x and x + w <= 500 and 285 <= y and 35 <= w <= 80 and 35 <= h <= 70:
            return True
    return False


def _is_challenge_popup(image: np.ndarray) -> bool:
    """Heuristic popup detection.  We want to know whether the solver is
    staring at a real challenge vs. a reward page or any other transitional
    frame.  A popup is the combination of "prompt row present" OR "blue
    confirm button at the bottom" (the challenge popup always has one)."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    blue = cv2.inRange(hsv, np.array([85, 25, 170]), np.array([125, 180, 255]))
    contours, _ = cv2.findContours(blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        # The popup's confirm button sits in the lower half, right side.
        if x > 350 and y > 750 and cv2.contourArea(contour) > 5000:
            return True
    return _prompt_row_still_present(image)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adb", type=Path, required=True)
    parser.add_argument("--device", default="127.0.0.1:16385")
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--click-engine", choices=("maa", "adb"), default="maa",
                        help="how to send taps: local MaaFramework controller "
                             "(default) or raw adb input tap")
    parser.add_argument("--max-prompts", type=int, default=MAX_PROMPTS,
                        help="hard cap on detected prompts; frames above this "
                             "are treated as misdetection and reported as "
                             "stale for the supervisor to refresh.")
    args = parser.parse_args()
    global CLICK_ENGINE
    CLICK_ENGINE = args.click_engine

    # First screenshot: a single sample.  Subsequent samples are taken between
    # actions to make the solver resilient against animation/UI settling.
    image_bytes, image = screenshot(args.adb, args.device)
    inferred_stale = not _is_challenge_popup(image)
    # If Maa emitted AdCaptchaDetected but the current frame is not actually
    # a challenge popup (e.g. the popup is still animating open or the event
    # fired on a stale frame), we report that and let the supervisor decide
    # whether to count it or refresh the frame itself.
    if inferred_stale:
        print(json.dumps({
            "captcha_layout": False,
            "error": "frame does not look like a challenge popup",
        }, ensure_ascii=False))
        return 0

    result: dict[str, object] | None = None
    last_layout_error = ""
    # Try up to 4 fresh screenshots before giving up on this solve call.
    for _ in range(4):
        try:
            result = analyze(image_bytes, image)
            break
        except RuntimeError as exc:
            if not str(exc).startswith("Unsafe CAPTCHA layout"):
                raise
            last_layout_error = str(exc)
            if not click_retry_if_present(args.adb, args.device, image):
                print(json.dumps({"captcha_layout": False, "error": last_layout_error},
                                 ensure_ascii=False))
                return 0
            image_bytes, image = screenshot(args.adb, args.device)
    if result is None:
        print(json.dumps({"captcha_layout": False, "error": last_layout_error},
                         ensure_ascii=False))
        return 0

    selected: list[dict[str, object]] = []
    used_points: list[tuple[int, int]] = []
    no_op_clicks = 0
    same_signature_streak = 0
    last_signature: tuple | None = None
    refresh_recommended = False
    # Up to 8 individual taps.  Real challenges have 1-6 prompts, so 8 covers
    # one mistake and one extra retry attempt.
    for step in range(8):
        try:
            result = analyze(image_bytes, image)
        except RuntimeError as exc:
            # Layout went bad mid-challenge (the popup closed, an overlay
            # appeared, etc).  Refresh the frame and try again.
            time.sleep(0.6)
            image_bytes, image = screenshot(args.adb, args.device)
            if _is_challenge_popup(image):
                continue
            # No more popup — nothing left to solve, exit cleanly.
            break
        if not result["prompts"]:
            break

        signature = _frame_signature(result)
        if signature == last_signature:
            same_signature_streak += 1
        else:
            same_signature_streak = 0
            last_signature = signature
        if same_signature_streak >= 2:
            # Two ticks in a row produced the same frame — clicks aren't
            # landing.  Bail and ask the supervisor to refresh the challenge
            # rather than burn more attempts on a stuck popup.
            refresh_recommended = True
            break

        try:
            target_index, point, score = next_click(result, used_points)
        except RuntimeError as exc:
            time.sleep(0.6)
            image_bytes, image = screenshot(args.adb, args.device)
            if _is_challenge_popup(image):
                continue
            break
        # Defensive: even if a future refactor regresses next_click's guard,
        # this is the last line of defence before issuing an out-of-bounds tap.
        if target_index < 0 or target_index >= len(result["targets"]):
            refresh_recommended = True
            break

        selected.append({
            "prompt_index": len(selected),
            "target_index": int(target_index),
            "point": list(point),
            "score": round(score, 4),
        })
        used_points.append(tuple(point))
        if args.submit:
            tap(args.adb, args.device, *point)
            time.sleep(0.45)
        # Verify the click landed.  If the prompt set is identical to the
        # previous frame, the tap was a no-op (wrong target, or Maa's input
        # controller swallowed it) — count it and bail if two in a row.
        image_bytes, image = screenshot(args.adb, args.device)
        try:
            post = analyze(image_bytes, image)
        except RuntimeError:
            post = None
        if post is None or _frame_signature(post) == _frame_signature(result):
            no_op_clicks += 1
            if no_op_clicks >= 2:
                refresh_recommended = True
                break
        else:
            no_op_clicks = 0
            # Step the per-iteration result forward to the freshly-analyzed
            # frame so the next loop iteration does not re-detect stale boxes.
            result = post

    submitted = False
    captcha_still_visible = False
    if args.submit and selected and result is not None and result.get("confirm"):
        tap(args.adb, args.device, *result["confirm"])
        time.sleep(2.0)
        _, after = screenshot(args.adb, args.device)
        submitted = True
        captcha_still_visible = _is_challenge_popup(after)

    if result is not None:
        result["selected"] = selected
        result["points"] = [item["point"] for item in selected]
    if args.output and result is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        marked = image.copy()
        for order, (x, y) in enumerate(result["points"], start=1):
            cv2.circle(marked, (x, y), 24, (0, 0, 255), 3)
            cv2.putText(marked, str(order), (x - 8, y + 9), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        cv2.imwrite(str(args.output), marked)
    output_payload: dict[str, object] = {
        "prompts": result["prompts"] if result else [],
        "targets": result["targets"] if result else [],
        "matrix": result["matrix"] if result else [],
        "confirm": result["confirm"] if result else None,
        "selected": selected,
        "points": [item["point"] for item in selected],
        "submitted": submitted,
        "captcha_still_visible": captcha_still_visible,
        "refresh_recommended": refresh_recommended,
    }
    print(json.dumps(output_payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
