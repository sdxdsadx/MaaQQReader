"""决定性判别: MAA swipe 到底有没有触到模拟器？

可能性: MAA controller 连接断/截图通道活着但触摸通道死了；
或验证码在 WebView 层吃不到 MAA 注入的触摸。
判据: 对同一个 client 发一个「打开通知栏再收起」的 swipe（下拉通知栏
y=10→600），看状态栏时间是否变化/通知栏是否出现——这能证明触摸通道活性。
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


def main() -> int:
    config = load_config("configs/qqreader.local.json")
    client = build_maa_client(config)
    client.connect()

    # 触摸活性测试: 从屏幕顶部下拉通知栏
    client.swipe(360, 8, 360, 620, 400)
    time.sleep(1.5)
    s1 = client.screencap()
    p1 = ACC / "probeC_open.png"
    p1.write_bytes(s1.data if hasattr(s1, "data") else s1)
    img1 = cv2.imdecode(np.fromfile(str(p1), dtype=np.uint8), cv2.IMREAD_COLOR)
    # 通知栏打开时顶部大面积是浅色
    top_brightness = img1[0:400, :].mean()
    print(f"[C] 下拉后顶部亮度 = {top_brightness:.0f}（通知栏打开应显著变亮/出现大面积浅色）")

    # 收起
    client.swipe(360, 620, 360, 8, 400)
    time.sleep(1.0)

    # adb input 直接对照实验（绕过 MAA 触摸通道）
    import subprocess
    adb = config.machine.adb_path
    dev = config.machine.adb_address
    subprocess.run([adb, "-s", dev, "shell", "input", "swipe", "168", "818", "260", "818", "600"],
                   capture_output=True, timeout=15)
    time.sleep(1.5)
    s2 = client.screencap()
    p2 = ACC / "probeC_adb.png"
    p2.write_bytes(s2.data if hasattr(s2, "data") else s2)
    img2 = cv2.imdecode(np.fromfile(str(p2), dtype=np.uint8), cv2.IMREAD_COLOR)
    blue = cv2.inRange(img2, (180, 50, 0), (255, 220, 180))
    blue = cv2.morphologyEx(blue, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cs, _ = cv2.findContours(blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    btn = None
    for c in cs:
        x, y, cw, ch = cv2.boundingRect(c)
        if cv2.contourArea(c) > 3000 and 60 <= cw <= 180:
            btn = (x, y, cw, ch)
            break
    print(f"[C] adb input 滑 92px 后按钮 = {btn}（原 (109,789,118,59)；若 x>109 则 adb 触摸有效，MAA 触摸通道死了）")

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
