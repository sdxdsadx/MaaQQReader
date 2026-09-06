"""Locate the QQ Reader ad-entry card (the "ad div") and the watch button inside it.

The MAA pipeline normally finds the ad entry by OCRing for "看小视频领好礼" /
"立即观看" / "(n/12)".  When the reward page is scrolled to a different section,
or the button text is rendered in a way the pipeline's OCR cannot read, the ad
flow fails with ``AdScrollToVideoCard`` max_hit.  This utility captures the
emulator screen, finds the ad card by its header/counter text boxes, treats the
union of those boxes as the ad "div", and returns the coordinate of the watch
button inside that div (the button is normally on the right side of the counter
row).  It can optionally click that point through the local MaaFramework
controller.

Usage::

    G:\\project_X\\.venv-captcha\\Scripts\\python.exe ad_locator.py \\
        --adb "D:\\...\\adb.exe" --device 127.0.0.1:16384 --output debug_ad.png

    # locate and click via local MAA
    ... ad_locator.py ... --click
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
import ddddocr
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MAA_CLICKER = ROOT / "tools" / "maa_click.py"

HEADER_PATTERNS = [
    re.compile(r"看小视频领好礼"),
    re.compile(r"看小视频再多领"),
    re.compile(r"看小视频"),
    re.compile(r"看广告"),
    re.compile(r"观看广告"),
]
BUTTON_PATTERNS = [
    re.compile(r"^立即观看$"),
    re.compile(r"^看小视频再多领$"),
    re.compile(r"^观看广告$"),
    re.compile(r"^看广告$"),
]
COUNTER_PATTERNS = [
    re.compile(r"每看完\s*\d+次.*?(\d+)/12"),
    re.compile(r"[（(]\s*\d{1,2}\s*/\s*12\s*[）)]"),
    re.compile(r"(\d{1,2})/12"),
]


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


def text_boxes(image_bytes: bytes, image: np.ndarray) -> list[dict[str, object]]:
    """Return OCR boxes with their recognised text for this screenshot."""
    detector = ddddocr.DdddOcr(det=True, ocr=False, show_ad=False)
    reader = ddddocr.DdddOcr(show_ad=False)
    boxes = detector.detection(image_bytes)
    results: list[dict[str, object]] = []
    for x1, y1, x2, y2 in boxes:
        crop = image[y1:y2, x1:x2]
        if crop.size == 0:
            continue
        try:
            text = reader.classification(crop)
        except Exception:
            text = ""
        text = (text or "").strip()
        if text:
            results.append({
                "box": [int(x1), int(y1), int(x2), int(y2)],
                "text": text,
            })
    return results


def match_boxes(entries: list[dict[str, object]], patterns: list[re.Pattern]) -> list[dict[str, object]]:
    matched = []
    for entry in entries:
        text = str(entry.get("text", ""))
        for pattern in patterns:
            if pattern.search(text):
                matched.append(entry)
                break
    return matched


_OCR_ITEM_RE = re.compile(
    r'\{"box":\[(\d+),(\d+),(\d+),(\d+)\],"score":[0-9.eE+-]+,"text":"((?:\\.|[^"\\])*)"\}'
)


def read_maa_ocr_entries(log_path: Path, max_entries: int = 300) -> list[dict[str, object]]:
    """Extract the latest OCR boxes/text from a MaaFramework log.

    MaaFramework writes full OCR results with ``box`` and ``text`` into
    ``maafw.log``.  Parsing those results is much more reliable than running a
    second OCR engine, and it lets us reconstruct the ad "div" from the same
    screen Maa already captured.  Only the most recent ``max_entries`` OCR items
    are kept so the result corresponds to the current on-screen frame, not the
    entire history.
    """
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    entries: list[dict[str, object]] = []
    for match in _OCR_ITEM_RE.finditer(text):
        x, y, w, h = map(int, match.groups()[:4])
        raw = match.group(5)
        try:
            parsed = json.loads(f'"{raw}"')
        except json.JSONDecodeError:
            parsed = raw
        entries.append({
            "box": [x, y, x + w, y + h],
            "text": str(parsed),
        })
    # Keep only the tail of the log (latest OCR batch/frame).
    entries = entries[-max_entries:]
    # De-duplicate repeated OCR items within that recent window.
    seen: set[tuple[int, int, int, int, str]] = set()
    latest: list[dict[str, object]] = []
    for entry in entries:
        key = (*entry["box"], str(entry["text"]))
        if key in seen:
            continue
        seen.add(key)
        latest.append(entry)
    return latest


def union_box(boxes: list[list[int]]) -> list[int]:
    xs1 = [b[0] for b in boxes]
    ys1 = [b[1] for b in boxes]
    xs2 = [b[2] for b in boxes]
    ys2 = [b[3] for b in boxes]
    return [min(xs1), min(ys1), max(xs2), max(ys2)]


def center(box: list[int]) -> list[int]:
    return [(box[0] + box[2]) // 2, (box[1] + box[3]) // 2]


def locate(image_bytes: bytes | None, image: np.ndarray,
           entries: list[dict[str, object]] | None = None) -> dict[str, object]:
    if entries is None:
        if image_bytes is None:
            return {"found": False, "error": "没有可用于识别的截图或日志"}
        entries = text_boxes(image_bytes, image)
    headers = match_boxes(entries, HEADER_PATTERNS)
    buttons = match_boxes(entries, BUTTON_PATTERNS)
    counters = match_boxes(entries, COUNTER_PATTERNS)

    # The ad "div" is the card containing the header and/or the counter.  If
    # only one is found, still treat it as the anchor and use the right side of
    # that row as the watch-button position.
    anchors = [b["box"] for b in [*headers, *counters]]
    if not anchors:
        return {
            "found": False,
            "error": "未找到广告卡片（缺少“看小视频领好礼”或“(n/12)”文案）",
            "entries": entries,
        }

    div = union_box(anchors)
    # Add a small margin around the card.
    margin_x = 20
    margin_y = 12
    div = [
        max(0, div[0] - margin_x),
        max(0, div[1] - margin_y),
        min(719, div[2] + margin_x),
        min(1279, div[3] + margin_y),
    ]

    point = None
    method = ""
    if buttons:
        # Prefer a real recognised watch button inside/near the card.
        inside = [b["box"] for b in buttons
                  if div[0] - 40 <= b["box"][0] and b["box"][2] <= div[2] + 40
                  and div[1] - 40 <= b["box"][1] and b["box"][3] <= div[3] + 40]
        if inside:
            point = center(inside[0])
            method = "button_ocr"
    if point is None and counters:
        counter = counters[0]["box"]
        # The watch button is on the right side of the same row as the counter.
        y = (counter[1] + counter[3]) // 2
        x = min(660, max(520, counter[2] + 80))
        point = [x, y]
        method = "counter_row_right"
    if point is None and headers:
        header = headers[0]["box"]
        y = (header[1] + header[3]) // 2
        x = min(660, max(520, header[2] + 90))
        point = [x, y]
        method = "header_row_right"

    return {
        "found": point is not None,
        "ad_div": div,
        "point": point,
        "method": method,
        "headers": [b["box"] for b in headers],
        "buttons": [b["box"] for b in buttons],
        "counters": [b["box"] for b in counters],
        "entries": entries,
    }


def tap(adb: Path, device: str, x: int, y: int, settle: float = 0.6,
        engine: str = "adb") -> bool:
    """Tap through local MAA controller, falling back to adb input tap."""
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


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", type=Path,
                        default=Path(r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"))
    parser.add_argument("--device", default="127.0.0.1:16385")
    parser.add_argument("--image", type=Path,
                        help="use a local screenshot instead of ADB capture (offline testing)")
    parser.add_argument("--log", type=Path,
                        help="read OCR boxes/text from a MaaFramework maafw.log "
                             "instead of running a separate OCR engine")
    parser.add_argument("--output", type=Path,
                        help="write annotated screenshot to this path")
    parser.add_argument("--click", action="store_true",
                        help="click the located watch button after finding it")
    parser.add_argument("--click-engine", choices=("maa", "adb"), default="adb")
    parser.add_argument("--swipe-up", type=int, default=0,
                        help="if no ad card is found, swipe up this many times "
                             "(each re-OCRing) before giving up; helps when the "
                             "video-entry card is below the current viewport")
    args = parser.parse_args()

    entries = read_maa_ocr_entries(args.log) if args.log and args.log.exists() else None

    def capture() -> tuple[bytes | None, np.ndarray | None]:
        if args.image and not capture._used:
            capture._used = True
            data = args.image.read_bytes()
            image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                return None, None
            return data, image
        try:
            return screenshot(args.adb, args.device)
        except Exception:
            if entries is None:
                raise
            return None, np.zeros((1280, 720, 3), np.uint8)

    capture._used = False

    data, image = capture()
    result = locate(data, image, entries)

    # The video-entry card may sit below the current viewport (the reward page
    # only shows it after scrolling).  Swipe up and re-OCR instead of failing.
    swipe = 0
    while (not result.get("found")) and swipe < args.swipe_up:
        swipe += 1
        try:
            adb_bytes(args.adb, args.device, "shell", "input", "swipe",
                      "360", "900", "360", "300", "400")
            time.sleep(1.2)
            data, image = capture()
            result = locate(data, image, None)
            result["swipe_up_attempt"] = swipe
        except Exception as exc:
            result = {"found": False, "error": str(exc)}
            break
    if args.output and result.get("found") and image is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        marked = image.copy()
        div = result["ad_div"]
        cv2.rectangle(marked, (div[0], div[1]), (div[2], div[3]), (0, 255, 0), 2)
        point = result["point"]
        cv2.circle(marked, tuple(point), 16, (0, 0, 255), 3)
        cv2.putText(marked, "watch", (point[0] - 30, point[1] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        cv2.imwrite(str(args.output), marked)
        result["output"] = str(args.output)

    clicked = False
    if args.click and result.get("found"):
        x, y = result["point"]
        clicked = tap(args.adb, args.device, x, y, engine=args.click_engine)
        result["clicked"] = clicked

    print(json.dumps(result, ensure_ascii=False))
    return 0 if (not args.click or clicked) else 1


if __name__ == "__main__":
    raise SystemExit(main())
