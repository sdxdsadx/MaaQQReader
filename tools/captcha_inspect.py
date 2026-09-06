"""Offline CAPTCHA screenshot inspector.

This utility only finds candidate objects and writes an annotated image.  It
does not choose an answer, click the emulator, or submit a CAPTCHA.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import ddddocr


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a CAPTCHA screenshot offline")
    parser.add_argument("image", type=Path, help="PNG/JPEG screenshot to inspect")
    parser.add_argument("--output", type=Path, help="annotated output image")
    args = parser.parse_args()

    source = args.image.resolve()
    output = (args.output or source.with_name(f"{source.stem}.detected.png")).resolve()
    image_bytes = source.read_bytes()

    detector = ddddocr.DdddOcr(det=True, ocr=False, show_ad=False)
    boxes = detector.detection(image_bytes)

    image = cv2.imread(str(source))
    if image is None:
        raise SystemExit(f"Unable to read image: {source}")

    for index, (x1, y1, x2, y2) in enumerate(boxes, start=1):
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.putText(
            image,
            str(index),
            (x1, max(18, y1 - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 0, 255),
            2,
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output), image)
    print(json.dumps({"source": str(source), "output": str(output), "boxes": boxes}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
