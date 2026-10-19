"""N: 找到触屏设备（ABS_MT 多点触屏，X 0-720 Y 0-1280）——sendevent 原始注入。
构造拟人轨迹: DOWN → 变速 MOVE 序列（快-慢-微过冲-回调）→ UP。
每步直接写 /dev/input/eventX。
协议（B 协议）: 0003 0039 (TRACKING_ID), 0003 0035/0036 (X/Y), 0001 014a (BTN_TOUCH), SYN 0000 0000 00000000。
"""
import random
import re
import subprocess
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

ACC = Path(r"G:\project_X\runtime\screenshots\19700104")


def get_touch_dev(adb, dev):
    r = subprocess.run([adb, "-s", dev, "shell", "getevent", "-pl"], capture_output=True, text=True, timeout=20)
    cur = None
    for line in r.stdout.splitlines():
        m = re.search(r"add device \d+: (/dev/input/event\d+)", line)
        if m:
            cur = m.group(1)
        if cur and "ABS_MT_POSITION_X" in line:
            return cur
    return None


def send(adb, dev, device, events):
    """events: [(type, code, value), ...] 一次写入多行 sendevent。"""
    script = "".join(f"sendevent {device} {t} {c} {v}; " for t, c, v in events)
    subprocess.run([adb, "-s", dev, "shell", script], capture_output=True, timeout=20)


def human_track(sx, sy, dx):
    """生成拟人轨迹点列: [(x, y, dt_ms), ...] 加速-匀速-减速-过冲-回调。"""
    pts = []
    over = random.randint(4, 9) * (1 if dx > 0 else -1)
    n = max(12, min(40, abs(dx) // 6))
    for i in range(1, n + 1):
        f = i / n
        # ease-out: 快起步慢结束
        ease = 1 - (1 - f) ** 2
        x = sx + int(dx * ease)
        y = sy + random.randint(-2, 2)
        dt = random.randint(14, 34)  # 每步 14-34ms
        pts.append((x, y, dt))
    # 过冲点
    pts.append((sx + dx + over, sy + random.randint(-1, 1), random.randint(20, 40)))
    # 微回调（1-2 步）
    pts.append((sx + dx, sy, random.randint(25, 50)))
    return pts


def main() -> int:
    config = load_config("configs/qqreader.local.json")
    adb = config.machine.adb_path
    dev = config.machine.adb_address
    client = build_maa_client(config)
    client.connect()

    tdev = get_touch_dev(adb, dev)
    print(f"[N] 触屏设备: {tdev}")
    if not tdev:
        client.close()
        return 1

    s = client.screencap()
    p = ACC / "liveN_t0.png"
    p.write_bytes(s.data if hasattr(s, "data") else s)
    d = detect_slide(p.read_bytes())
    if not d.found:
        print("[N] 检测失败:", d.error)
        client.close()
        return 1
    sx, sy = d.slider_center
    dx = d.distance
    print(f"[N] 起点({sx},{sy}) 距离{dx} → sendevent 拟人轨迹")

    # DOWN
    send(adb, dev, tdev, [(3, 57, 0), (3, 53, sx), (3, 54, sy), (1, 330, 1), (0, 0, 0)])
    time.sleep(0.05)
    # MOVE 变速
    for x, y, dt in human_track(sx, sy, dx):
        send(adb, dev, tdev, [(3, 53, x), (3, 54, y), (0, 0, 0)])
        time.sleep(dt / 1000.0)
    time.sleep(random.uniform(0.08, 0.2))
    # UP
    send(adb, dev, tdev, [(3, 57, -1), (1, 330, 0), (0, 0, 0)])
    time.sleep(2.5)

    s2 = client.screencap()
    ocr = client.recognize("OCR", {}, s2)
    dd = ocr.detail if isinstance(ocr.detail, dict) else {}
    items = dd.get("all") or dd.get("boxes") or dd.get("items") or []
    joined = " ".join(str(i.get("text")) for i in items if isinstance(i, dict))
    ok = "安全验证" not in joined and "滑块" not in joined and "验证" not in joined
    print(f"[N] 结果: {'✅ 通过!!' if ok else '❌ 仍失败'} | 文案: {joined[:110]}")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
