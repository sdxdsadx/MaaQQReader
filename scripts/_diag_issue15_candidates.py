"""issue #15 临时诊断：批量验证候选验证码截图。"""
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

CANDIDATES = [
    _ROOT / "runtime/screenshots/ad_watch/captcha_scene_1.png",
    _ROOT / "runtime/screenshots/19700105/autocap_r1_pre.png",
    _ROOT / "runtime/screenshots/19700105/autocap_r2_pre.png",
    _ROOT / "runtime/screenshots/19700104/live2_r1.png",
    _ROOT / "runtime/screenshots/19700104/live2_r3.png",
]

for png in CANDIDATES:
    if not png.is_file():
        print(f"[MISS] {png.name}")
        continue
    data = png.read_bytes()
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    d = detect_slide(data)
    print(f"\n== {png} ({len(data)}B) shape={img.shape}")
    print("   detect:", d)
    if img is not None:
        track, slider = _find_track_and_slider(img)
        print("   track:", track, "slider:", slider)
        if track is not None and slider is not None:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            gap = _find_gap_x(gray, track, slider)
            print("   strict gap_x:", gap,
                  "" if gap is None else f"distance={gap - (slider[0] + slider[2] // 2)}")
