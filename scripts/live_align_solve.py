"""终局方案: motionevent 按住-分段-精对齐-松手。
E0 显示按住时按钮在 212 头在 494。若我们按住不松，逐 px 挪并实时比对拼图
头与缺口 Canny 位置，对准后再 UP——绕开回弹，一次通过。

实现: adb motionevent DOWN(按钮) → 循环: MOVE(dx) + screencap + 算
「头 x vs 缺口 x」差 → 未对准继续 MOVE → 对准(±4px) → UP。
每次 MOVE 后轻等 0.35s（截图+计算）。上限 40 步防死循环。
"""
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

ACC = _ROOT / "runtime/screenshots/19700104"


def head_and_gap(img):
    """返回 (拼图头x, 缺口x)。缺口: 轨道上方图块里的拼图缺口阴影。"""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # 头: 拼图区右移中的强竖边（限制在拼图容器 y600..800）
    e = cv2.Canny(g[600:800, :], 50, 150)
    col = e.sum(axis=0) / max(1, e.shape[0])
    sm = np.convolve(col, np.ones(9) / 9, mode="same")
    head = int(np.argmax(sm[60:]) + 60)
    # 缺口: detect_slide 的 target（在完整图上）
    ok, data = cv2.imencode(".png", img)
    d = detect_slide(data.tobytes())
    gap = (d.slider_center[0] + d.distance) if d.found else None
    return head, gap


def main() -> int:
    config = load_config("configs/qqreader.local.json")
    adb = config.machine.adb_path
    dev = config.machine.adb_address
    client = build_maa_client(config)
    client.connect()

    def snap(tag):
        s = client.screencap()
        p = ACC / f"probeF_{tag}.png"
        p.write_bytes(s.data if hasattr(s, "data") else s)
        return cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)

    img0 = snap("start")
    head0, gap = head_and_gap(img0)
    if gap is None:
        print("[F] 检测不到缺口（验证码可能不在屏）")
        client.close()
        return 1
    print(f"[F0] head={head0} gap={gap} 需右移≈{gap-head0}px（按住状态）")

    # 按下
    subprocess.run([adb, "-s", dev, "shell", "input", "motionevent", "DOWN", "168", "818"],
                   capture_output=True, timeout=15)
    time.sleep(0.4)

    cur = 168
    step = 15 if gap > head0 else -15
    for i in range(40):
        remain = gap - head0
        if abs(remain) <= 5:
            break
        # 接近时缩小步长
        use = step if abs(remain) > 30 else max(2, int(abs(remain) / 3)) * (1 if remain > 0 else -1)
        cur += use
        subprocess.run([adb, "-s", dev, "shell", "input", "motionevent", "MOVE", str(cur), "818"],
                       capture_output=True, timeout=15)
        time.sleep(0.35)
        img = snap(f"m{i}")
        head0, gap2 = head_and_gap(img)
        gap = gap2 if gap2 else gap
        print(f"  move#{i} x={cur} → 头={head0} 缺口={gap} 余={gap-head0}")
        if abs(gap - head0) <= 5:
            break

    # 松手
    subprocess.run([adb, "-s", dev, "shell", "input", "motionevent", "UP", str(cur), "818"],
                   capture_output=True, timeout=15)
    time.sleep(2.0)
    img = snap("end")
    # 判定: 验证码还在吗（找「安全验证」特征：顶部标题区 OCR 不可用这里用色块）
    blue = cv2.inRange(img, (180, 50, 0), (255, 220, 180))
    blue = cv2.morphologyEx(blue, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cs, _ = cv2.findContours(blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    btn = None
    for c in cs:
        x, y, cw, ch = cv2.boundingRect(c)
        if cv2.contourArea(c) > 3000 and 60 <= cw <= 180:
            btn = (x, y)
            break
    print(f"[F-end] 按钮={btn}（若回到 109 → 失败回弹；若停在中间/消失 → 可能通过）")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
