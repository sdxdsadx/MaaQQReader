"""回到书架页（阅读时长已 640 分钟）。点「时长兑赠币，立即领取>」
(y=194) 进奖励中心，找阅读卡领 2 个相邻代币奖励。"""
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
client.swipe(200, 204, 200, 204, 60)
time.sleep(3)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
for t, b in sorted(boxes, key=lambda x: x[1][1]):
    if any(k in t for k in ("再读", "已读", "阅读", "领取", "赠币", "分钟", "去")):
        print(f"y={b[1]:4d} x={b[0]:4d} w={b[2]:3d} | {t}")
client.close()
