"""确认跨日重置：10 分钟/30 分钟档按钮都变回「领取」（未领取状态），
「今日再读N分钟」行没刷出来（可能在加载或需再下滑）。
今日已获赠币=10（签到 5+5）。
现在阅读时长 146 分钟是今天（00:29-05:12 的滑动阅读全算今天）！
→ 10 分钟档 + 30 分钟档 + 45 分钟档 + …全部可领！
狂点所有「领取」按钮循环收割。"""
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

total_rounds = 0
last_coins = ""
for round_no in range(20):
    boxes = client.recognize("OCR", {}, client.screencap()).text_boxes()
    claim = [(t, b) for t, b in boxes if t.strip() == "领取"]
    if not claim:
        # 下滑找更多
        client.swipe(360, 1100, 360, 600, 400)
        time.sleep(1.8)
        boxes = client.recognize("OCR", {}, client.screencap()).text_boxes()
        claim = [(t, b) for t, b in boxes if t.strip() == "领取"]
    if not claim:
        print(f"[{round_no}] 无更多领取按钮，停", flush=True)
        break
    t, b = claim[0]
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(2.5)
    c = coins()
    print(f"[{round_no}] 领取后: {c}", flush=True)
    if c == last_coins and round_no > 2:
        total_rounds += 1
        if total_rounds >= 2:
            break
    else:
        total_rounds = 0
    last_coins = c

print("最终:", coins(), flush=True)
client.close()
