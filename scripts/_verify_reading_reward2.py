"""入口文案是「时长兑赠币，立即领取>」(y=194)。点它进奖励页读赠币数。"""
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
s = client.screencap()
for t, b in client.recognize("OCR", {}, s).text_boxes():
    if "时长兑赠币" in t:
        x, y = b[0] + b[2] // 2, b[1] + b[3] // 2
        print(f"点「{t}」@ ({x},{y})")
        client.swipe(x, y, x, y, 80)
        break
time.sleep(3)
s2 = client.screencap()
for t, b in sorted(client.recognize("OCR", {}, s2).text_boxes(), key=lambda x: x[1][1])[:10]:
    print(f"y={b[1]:4d} | {t}")
client.close()
