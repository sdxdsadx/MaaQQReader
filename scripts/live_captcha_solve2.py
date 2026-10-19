"""继续收敛: 用实测 scale=5.44 + 每轮差分反馈，迭代到验证码消失。"""
import random
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
SCALE = 5.44


def shot(client, tag):
    s = client.screencap()
    p = ACC / f"live2_{tag}.png"
    p.write_bytes(s.data if hasattr(s, "data") else s)
    ocr = client.recognize("OCR", {}, s)
    d = ocr.detail if isinstance(ocr.detail, dict) else {}
    items = d.get("all") or d.get("boxes") or d.get("items") or []
    return p, " ".join(str(i.get("text")) for i in items if isinstance(i, dict))


def head_x(png: Path) -> int:
    img = cv2.imdecode(np.fromfile(str(png), dtype=np.uint8), cv2.IMREAD_COLOR)
    g = cv2.cvtColor(img[600:800, :], cv2.COLOR_BGR2GRAY)
    e = cv2.Canny(g, 50, 150)
    col = e.sum(axis=0) / max(1, e.shape[0])
    sm = np.convolve(col, np.ones(9) / 9, mode="same")
    return int(np.argmax(sm))


def btn_center(png: Path):
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
    dur = max(300, min(800, int(abs(dx) * 2.2))) + random.randint(-50, 100)
    over = random.randint(2, 6) if dx > 0 else -random.randint(2, 6)
    client.swipe(sx, sy, sx + dx + over, sy, dur)
    time.sleep(random.uniform(0.08, 0.15))
    client.swipe(sx + dx + over, sy, sx + dx, sy, random.randint(160, 300))


def main() -> int:
    config = load_config("configs/qqreader.local.json")
    client = build_maa_client(config)
    client.connect()

    for round_no in range(1, 5):
        p, joined = shot(client, f"r{round_no}")
        if "安全验证" not in joined and "滑块" not in joined:
            print(f"[round{round_no}] ✅ 验证码已消失！文案头: {joined[:80]}")
            client.close()
            return 0
        d = detect_slide(p.read_bytes())
        if not d.found:
            print(f"[round{round_no}] detect 失败: {d.error!r}（可能题面已换，重跑 detect 下一轮）")
            continue
        btn = btn_center(p)
        head = head_x(p)
        gap_x = d.slider_center[0] + d.distance
        delta_head = gap_x - head
        dx = int(round(delta_head / SCALE))
        print(f"[round{round_no}] 按钮={btn} 头={head} 缺口={gap_x} 头距缺口={delta_head} → 滑 {dx}px")
        if abs(dx) < 3:
            print("[round] 距离过小，改用微调 3px")
            dx = 3 if delta_head > 0 else -3
        humanized(client, btn[0], btn[1], dx)
        time.sleep(2.0)

    p, joined = shot(client, "final")
    print(f"[final] {'❌ 仍弹窗' if '安全验证' in joined else '✅ 通过'}")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
