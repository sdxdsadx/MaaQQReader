"""关键疑点: 按钮中心四轮恒 (168,818)？滑动后按钮应移动。两种可能:
A. 每次 swipe 后按钮/题目被重置（验证码每轮失败重置拼图）
B. 我们滑的根本不是验证码的滑块（168,818 是页面别的蓝色元素）

判据: 连续两张截图（不滑动）按钮是否恒定；再滑 1px 看按钮动不动。
另外 r1 的实移比 -223/-41=5.44 与本题缺口的收敛（67→37→37 不动）矛盾
——头不动的轮次说明 swipe 起点错了（滑到别的 UI 上）。
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


def btn_center(img):
    blue = cv2.inRange(img, (180, 50, 0), (255, 220, 180))
    blue = cv2.morphologyEx(blue, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cs, _ = cv2.findContours(blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cs:
        x, y, cw, ch = cv2.boundingRect(c)
        a = cv2.contourArea(c)
        if a > 300:
            out.append((x, y, cw, ch, int(a)))
    return out


def main() -> int:
    config = load_config("configs/qqreader.local.json")
    client = build_maa_client(config)
    client.connect()

    s0 = client.screencap()
    (ACC / "probe_a.png").write_bytes(s0.data if hasattr(s0, "data") else s0)
    print("A0 蓝色轮廓:", btn_center(cv2.imdecode(np.fromfile(str(ACC / 'probe_a.png'), dtype=np.uint8), cv2.IMREAD_COLOR)))

    # 微滑 1px: 起点用 (168,818)
    client.swipe(168, 818, 169, 818, 200)
    time.sleep(1.5)

    s1 = client.screencap()
    (ACC / "probe_b.png").write_bytes(s1.data if hasattr(s1, "data") else s1)
    b1 = btn_center(cv2.imdecode(np.fromfile(str(ACC / 'probe_b.png'), dtype=np.uint8), cv2.IMREAD_COLOR))
    print("A1(滑1px后) 蓝色轮廓:", b1)

    # 反向微滑 5px 拉回
    client.swipe(169, 818, 164, 818, 200)
    time.sleep(1.5)
    s2 = client.screencap()
    (ACC / "probe_c.png").write_bytes(s2.data if hasattr(s2, "data") else s2)
    print("A2(回5px后) 蓝色轮廓:", btn_center(cv2.imdecode(np.fromfile(str(ACC / 'probe_c.png'), dtype=np.uint8), cv2.IMREAD_COLOR)))

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
