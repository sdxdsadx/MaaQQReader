"""注意：翻页结束回书架，但书架页显示「15分钟 / 领454赠币」——
「本周阅读时长/领赠币>」入口（y=194 是每周入口，不是每日时长卡）。
且每日阅读进度卡没显示（书架卡位换成了每周入口）。
进奖励中心全面验收：点 y=194 行。"""
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
client.swipe(150, 204, 150, 204, 60)
time.sleep(3)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
for t, b in sorted(boxes, key=lambda x: x[1][1]):
    if any(k in t for k in ("已获赠币", "再读", "已听", "领取", "分钟")):
        print(f"y={b[1]:4d} x={b[0]:4d} w={b[2]:3d} | {t}", flush=True)
client.close()
