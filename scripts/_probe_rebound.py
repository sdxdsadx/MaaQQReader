"""所有注入路径（MAA/adb input/touchscreen/motionevent）都动不了按钮。
但 r2/r6 里按钮明明滑过（BLOCKED 截图里按钮在 (168,818) 起点而拼图头大移位）…

再想: 探针里按钮中心恒 (168,818) = 起点 = 我们每次都从起点滑。
真相可能极简单: **每次滑动后验证码校验失败，拼图和按钮都自动回弹到起点**。
r2 拼图头 197→638 是滑动过程中（截到的是滑动后未回弹的瞬间？不，截图在回弹后）
——回弹的话应该回 197。除非 r2 那次截图在回弹前。

新判据: 滑动后立即连拍（0.3s/0.8s/1.5s/2.5s），看按钮/拼图头轨迹——
如果移动后又回弹，会看到「到过 260 又回 168」的过程 → 说明触摸有效但校验拒绝
（每次都拒）。那问题就纯粹是「缺口对不准」或「轨迹指纹被识别」，
而按钮回弹正好解释所有轮次按钮恒在起点！

如果回弹: 拼图头真位移无法用滑动后截图测（已回弹）→ r2 的 441px 是
滑动中途截图。那 scale 测量要在滑动中截——不可行。改为: 首滑按 r2 比例
206→441 反推真实 needs≈? 不可能从一次拒绝推出正确距离。

正确路线: 逐步加大滑动距离二分试探（滑→若失败自动换新题→再滑更大/更小），
记录每轮「题目类型+滑动距离+结果」，凑出通过条件。或者直接长按轨道左端点
再慢拖（人类按住的是滑块图标中央而非中心点）。
"""
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import cv2
import numpy as np

from qqreader.captcha.slide import detect_slide
from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

ACC = _ROOT / "runtime/screenshots/19700104"


def snap(client, tag):
    s = client.screencap()
    p = ACC / f"probeE_{tag}.png"
    p.write_bytes(s.data if hasattr(s, "data") else s)
    return cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)


def btn(img):
    blue = cv2.inRange(img, (180, 50, 0), (255, 220, 180))
    blue = cv2.morphologyEx(blue, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cs, _ = cv2.findContours(blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in cs:
        x, y, cw, ch = cv2.boundingRect(c)
        if cv2.contourArea(c) > 3000 and 60 <= cw <= 180:
            return (x, y, cw, ch)
    return None


def head_x(img):
    g = cv2.cvtColor(img[600:800, :], cv2.COLOR_BGR2GRAY)
    e = cv2.Canny(g, 50, 150)
    col = e.sum(axis=0) / max(1, e.shape[0])
    sm = np.convolve(col, np.ones(9) / 9, mode="same")
    return int(np.argmax(sm))


def main() -> int:
    config = load_config("configs/qqreader.local.json")
    client = build_maa_client(config)
    client.connect()

    # 回弹轨迹观察: 快速连拍
    client.swipe(168, 818, 268, 818, 500)
    for i, wait in enumerate((0.2, 0.6, 1.2, 2.0)):
        time.sleep(wait)
        img = snap(client, f"e{i}")
        print(f"E{i} (+{wait}s): 按钮={btn(img)} 头={head_x(img)}")

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
