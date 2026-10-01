"""决定性实验: 对当前挂在屏幕上的滑块验证码做活体求解闭环。

流程: 截图 t0 → detect_slide → 按先验 scale 修正滑动 → 截图 t1 复核
→ 若仍在: 差分实测拼图头真实位移 → 按真实比例补滑 → 截图 t2 终判。
全程打印坐标证据。
"""
import re
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
SCALE = 2.14


def shot(client, tag):
    s = client.screencap()
    p = ACC / f"live_{tag}.png"
    p.write_bytes(s.data if hasattr(s, "data") else s)
    ocr = client.recognize("OCR", {}, s)
    d = ocr.detail if isinstance(ocr.detail, dict) else {}
    items = d.get("all") or d.get("boxes") or d.get("items") or []
    texts = [str(i.get("text")) for i in items if isinstance(i, dict)]
    print(f"[{tag}] saved {p.name}; ocr_n={len(texts)}")
    return p, texts


def head_x(png: Path) -> int:
    """拼图区(y600-800)最强竖边缘 x。"""
    img = cv2.imdecode(np.fromfile(str(png), dtype=np.uint8), cv2.IMREAD_COLOR)
    g = cv2.cvtColor(img[600:800, :], cv2.COLOR_BGR2GRAY)
    e = cv2.Canny(g, 50, 150)
    col = e.sum(axis=0) / max(1, e.shape[0])
    sm = np.convolve(col, np.ones(9) / 9, mode="same")
    return int(np.argmax(sm))


def button_center(png: Path):
    img = cv2.imdecode(np.fromfile(str(png), dtype=np.uint8), cv2.IMREAD_COLOR)
    blue = cv2.inRange(img, (180, 50, 0), (255, 220, 180))
    blue = cv2.morphologyEx(blue, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cs, _ = cv2.findContours(blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in cs:
        x, y, cw, ch = cv2.boundingRect(c)
        if cv2.contourArea(c) > 3000 and 60 <= cw <= 180:
            return (x + cw // 2, y + ch // 2)
    return None


def humanized(client, sx, sy, dx):
    import random
    dur = max(350, min(900, int(abs(dx) * 2.2))) + random.randint(-60, 120)
    over = random.randint(3, 8) if dx > 0 else -random.randint(3, 8)
    client.swipe(sx, sy, sx + dx + over, sy, dur)
    time.sleep(random.uniform(0.08, 0.18))
    client.swipe(sx + dx + over, sy, sx + dx, sy, random.randint(180, 320))


def main() -> int:
    config = load_config("configs/qqreader.local.json")
    client = build_maa_client(config)
    client.connect()
    print("[live] connected", flush=True)

    p0, texts0 = shot(client, "t0")
    joined0 = " ".join(texts0)
    print(f"[t0] 文案: {joined0[:120]}")
    if not ("安全验证" in joined0 or "滑块" in joined0):
        print("[live] 屏幕上没有验证码弹窗（可能已过期/被关闭）")
        client.close()
        return 0

    d0 = detect_slide(p0.read_bytes())
    print(f"[t0] detect: found={d0.found} err={d0.error!r}")
    if not d0.found:
        client.close()
        return 1
    sx, sy = d0.slider_center
    gap_x = d0.slider_center[0] + d0.distance
    head0 = head_x(p0)
    btn0 = button_center(p0)
    print(f"[t0] 按钮={d0.slider} 中心={d0.slider_center} 缺口gap_x={gap_x} raw={d0.distance}")
    print(f"[t0] 拼图头边缘x={head0} 蓝按钮实测中心={btn0}")

    # 首滑: (gap - head0)/scale —— 用拼图头真实起点（边缘峰）而非按钮中心
    first = int(round((gap_x - head0) / SCALE))
    print(f"[live] 首滑 {first}px（(gap {gap_x} - head0 {head0})/2.14）")
    humanized(client, sx, sy, first)
    time.sleep(2.0)

    p1, texts1 = shot(client, "t1")
    j1 = " ".join(texts1)
    still1 = "安全验证" in j1
    print(f"[t1] 仍弹窗={still1} | 文案: {j1[:100]}")
    if not still1:
        print("[live] ✅ 首滑即通过！")
        client.close()
        return 0

    head1 = head_x(p1)
    moved = head1 - head0
    real_scale = moved / first if first else 0
    print(f"[t1] 拼图头 {head0}→{head1} 实移{moved}px / 按钮滑{first}px → 真实scale={real_scale:.2f}")
    d1 = detect_slide(p1.read_bytes())
    if d1.found:
        gap1 = d1.slider_center[0] + d1.distance
        delta_head = gap1 - head1
        add = int(round(delta_head / (real_scale if real_scale > 0.5 else SCALE)))
        print(f"[t1] 新缺口gap_x={gap1} 头距缺口{delta_head}px → 补滑 {add}px")
        btn1 = d1.slider_center
        humanized(client, btn1[0], btn1[1], add)
        time.sleep(2.0)
        p2, texts2 = shot(client, "t2")
        j2 = " ".join(texts2)
        print(f"[t2] 仍弹窗={'安全验证' in j2} | 文案: {j2[:100]}")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
