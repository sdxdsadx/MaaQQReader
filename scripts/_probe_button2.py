"""决定性发现: 滑 1px 按钮纹丝不动（(109,789,118,59) 恒定）——
MAA 的 click/swipe 坐标系与屏幕显示坐标有偏移，或者 swipe 没落在按钮上。

r6 实测按钮滑 339px 后 BLOCKED 截图里按钮仍在 (168,818) 附近 = 按钮从没动过！
而 r2 的拼图头 197→638 大移位，可能是滑动落点碰巧拨到了拼图图块本身。

新假设: MAA swipe 起点必须按住 500ms 再拖（touch-and-hold），或者
验证码的滑块要用「按住拼图头」而不是「按住轨道按钮」来拖。

实验 B: 用 mouse 模式长按拖拽——MAA client 的 swipe 已带 duration;
试在按钮中心 (168,818) 按 800ms 慢速拖 30px，看按钮动不动;
再试直接按在拼图头 (约 head 位置 y=700) 拖 30px 对比。
"""
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import cv2
import numpy as np

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

ACC = _ROOT / "runtime/screenshots/19700104"


def btn(img):
    blue = cv2.inRange(img, (180, 50, 0), (255, 220, 180))
    blue = cv2.morphologyEx(blue, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cs, _ = cv2.findContours(blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in cs:
        x, y, cw, ch = cv2.boundingRect(c)
        if cv2.contourArea(c) > 3000 and 60 <= cw <= 180:
            return (x, y, cw, ch)
    return None


def main() -> int:
    config = load_config("configs/qqreader.local.json")
    client = build_maa_client(config)
    client.connect()

    def snap(tag):
        s = client.screencap()
        p = ACC / f"probeB_{tag}.png"
        p.write_bytes(s.data if hasattr(s, "data") else s)
        img = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)
        return p, btn(img)

    # B1: 慢速长时拖按钮 30px（800ms）
    client.swipe(168, 818, 198, 818, 800)
    time.sleep(1.5)
    p, b = snap("b1_slow30")
    print(f"B1 慢拖30px后 按钮={b}")

    # B2: 快速回 30px
    client.swipe(198, 818, 168, 818, 300)
    time.sleep(1.5)
    p, b = snap("b2_back")
    print(f"B2 拉回后 按钮={b}")

    # B3: 按在拼图头（y=710 高一点）拖 30px
    client.swipe(168, 710, 198, 710, 800)
    time.sleep(1.5)
    p, b = snap("b3_head_y710")
    print(f"B3 拼图头y710拖30px后 按钮={b}")

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
