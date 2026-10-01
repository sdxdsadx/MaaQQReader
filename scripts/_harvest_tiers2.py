"""✅ 突破：签到浮层是元凶！关闭后 10 分钟档 +20（10→30）、30 分钟档 +20
（30→50）全部到手！今日 50 赠币。
继续：下滑看还有没有 45/60 分钟等更高档位可领（146 分钟时长应该够
好几档）。循环收割所有「领取」。"""
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()

def coins():
    s = client.screencap()
    for t, b in client.recognize("OCR", {}, s).text_boxes():
        if "今日已获赠币" in t:
            return t
    return "?"

stale = 0
for round_no in range(25):
    boxes = client.recognize("OCR", {}, client.screencap()).text_boxes()
    claim = [(t, b) for t, b in boxes if t.strip() == "领取"]
    if not claim:
        client.swipe(360, 1150, 360, 550, 450)
        time.sleep(1.8)
        boxes = client.recognize("OCR", {}, client.screencap()).text_boxes()
        claim = [(t, b) for t, b in boxes if t.strip() == "领取"]
    if not claim:
        print(f"[{round_no}] 无更多领取", flush=True)
        break
    t, b = claim[0]
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(2.5)
    c = coins()
    print(f"[{round_no}] {c}", flush=True)
    if c == "今日已获赠币 50":
        stale += 1
        if stale >= 3:
            print("连续 3 轮无变化，停", flush=True)
            break

print("最终:", coins(), flush=True)
client.close()
