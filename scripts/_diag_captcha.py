"""诊断: 对真实验证码截图跑 detect_slide，输出轨道/滑块/缺口坐标。"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import glob

from qqreader.captcha.slide import detect_slide

shots = sorted(
    glob.glob(r"G:\project_X\runtime\screenshots\19700104\*CAPTCHA*.png")
    + glob.glob(r"G:\project_X\runtime\screenshots\19700104\*BLOCKED*.png"),
    key=lambda p: Path(p).stat().st_mtime,
    reverse=True,
)
for path in shots[:4]:
    data = Path(path).read_bytes()
    d = detect_slide(data)
    print(f"--- {Path(path).name[-40:]}")
    print(f"  found={d.found} error={d.error!r}")
    if d.found or d.track != (0, 0, 0, 0):
        print(f"  track={d.track} slider={d.slider}")
        print(f"  slider_center={d.slider_center} target={d.target} distance={d.distance}")
