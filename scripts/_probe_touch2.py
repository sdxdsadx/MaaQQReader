"""终判: adb input 也不动按钮 + 通知栏没下拉成功?
查 maa 触摸通道是否真的断了 & adb input 是否真的发出去（看返回码）。
另外试 adb shell input keyevent 回 HOME 再回来，验证 adb 通道活性。
最后用 sendevent 原始触摸 或 input touchscreen swipe（触屏源）再试。"""
import subprocess
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
    adb = config.machine.adb_path
    dev = config.machine.adb_address
    client = build_maa_client(config)
    client.connect()

    def snap(tag):
        s = client.screencap()
        p = ACC / f"probeD_{tag}.png"
        p.write_bytes(s.data if hasattr(s, "data") else s)
        return btn(cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR))

    # D1: input touchscreen swipe（明确触屏源）
    r = subprocess.run([adb, "-s", dev, "shell", "input", "touchscreen", "swipe",
                        "168", "818", "300", "818", "700"], capture_output=True, text=True, timeout=15)
    print(f"D1 touchscreen swipe rc={r.returncode} err={r.stderr.strip()[:80]}")
    time.sleep(1.5)
    print(f"D1 后按钮 = {snap('d1')}")

    # D2: 分解 gesture: input motionevent DOWN/MOVE/UP（Android 11+ 支持 motionevent）
    r = subprocess.run([adb, "-s", dev, "shell", "input", "motionevent", "DOWN", "168", "818"],
                       capture_output=True, text=True, timeout=15)
    print(f"D2a motionevent DOWN rc={r.returncode} err={r.stderr.strip()[:60]}")
    time.sleep(0.3)
    for x in (200, 240, 280):
        subprocess.run([adb, "-s", dev, "shell", "input", "motionevent", "MOVE", str(x), "818"],
                       capture_output=True, text=True, timeout=15)
        time.sleep(0.15)
    r = subprocess.run([adb, "-s", dev, "shell", "input", "motionevent", "UP", "280", "818"],
                       capture_output=True, text=True, timeout=15)
    print(f"D2b motionevent UP rc={r.returncode} err={r.stderr.strip()[:60]}")
    time.sleep(1.5)
    print(f"D2 后按钮 = {snap('d2')}")

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
