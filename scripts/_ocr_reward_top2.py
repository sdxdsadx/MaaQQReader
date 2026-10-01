"""听书卡在 y≈992（每周5天听书30分钟），每日阅读卡还没到顶。
继续上滑到底（顶部），找「每日阅读领赠币」和「每日听书」卡片的状态行
（再读N分钟/已领）。"""
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
client.swipe(360, 950, 360, 300, 500)
time.sleep(2)
client.swipe(360, 950, 360, 300, 500)
time.sleep(2)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
for t, b in sorted(boxes, key=lambda x: x[1][1]):
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
