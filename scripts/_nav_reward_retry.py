"""点入口后没进奖励页（OCR 还显示书架 146分钟）——入口行点击位置
(165+100,204+10)=(265,214) 可能偏。直接点行中心 (165,204)。重试并
用 OCR 确认「已获赠币」出现。"""
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
    return None

for attempt in range(3):
    if coins():
        print(f"[{attempt}] 已在奖励页:", coins(), flush=True)
        break
    s = client.screencap()
    entry = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes()
             if "兑赠币" in t]
    if entry:
        t, b = entry[0]
        client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
        time.sleep(3)
        print(f"[{attempt}] 点入口重试", flush=True)
    else:
        client.swipe(360, 400, 360, 1100, 400)  # 回顶部
        time.sleep(2)

client.close()
