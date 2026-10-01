"""在奖励页但「看小视频领好礼/立即观看」区域在更下方（当前可见到 y=1257
每周阅读600分钟卡）。广告区在每周卡下面，继续下滑找。"""
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
client.swipe(360, 1100, 360, 400, 600)
time.sleep(2)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
for t, b in sorted(boxes, key=lambda x: x[1][1]):
    if any(k in t for k in ("立即观看", "看小视频", "礼物", "广告")):
        print(f"y={b[1]:4d} x={b[0]:4d} w={b[2]:3d} | {t}", flush=True)
client.close()
