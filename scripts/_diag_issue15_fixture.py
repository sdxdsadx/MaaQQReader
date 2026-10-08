"""issue #15 临时诊断：真实验证码 fixture 上跑 detect_slide 全链路。"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import cv2
import numpy as np

from qqreader.captcha.slide import (
    _find_gap_x,
    _find_track_and_slider,
    detect_slide,
)

PNG = _ROOT / "runtime" / "screenshots" / "ad_watch" / "captcha_now.png"
data = PNG.read_bytes()
print("fixture size:", len(data), "PNG magic:", data[:8])

img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
print("decoded shape:", None if img is None else img.shape)

d = detect_slide(data)
print("detect_slide:", d)

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
track, slider = _find_track_and_slider(img)
print("track:", track, "slider:", slider)
if track is not None and slider is not None:
    gap = _find_gap_x(gray, track, slider)
    print("strict gap_x:", gap)
    if gap is not None:
        print("distance would be:", gap - (slider[0] + slider[2] // 2))
