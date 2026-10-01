"""奖励页：赠币 80→120（+40 自动入账：签到+阅读档位？）。
阅读档位「10分钟/30分钟」的领取按钮在 y=1176。点两个领取按钮；
再下滑找听书卡（每日听书30分钟+20赠币）。"""
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

client.swipe(216, 1189, 216, 1189, 60); time.sleep(2.5)
print("10分钟档后:", coins(), flush=True)
client.swipe(502, 1189, 502, 1189, 60); time.sleep(2.5)
print("30分钟档后:", coins(), flush=True)
client.swipe(360, 1100, 360, 500, 500); time.sleep(2)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
for t, b in sorted(boxes, key=lambda x: x[1][1]):
    if "听书" in t or "已听" in t:
        print(f"听书行: y={b[1]:4d} x={b[0]:4d} w={b[2]:3d} | {t}", flush=True)
client.close()
