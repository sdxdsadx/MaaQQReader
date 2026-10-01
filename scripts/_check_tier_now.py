"""翻页 67 次完成，回书架（15分钟——显示没变？书架「15分钟」可能是本周卡
缓存）。注意：_page20_v2 的回奖励页逻辑没触发（BACK 后没找到入口行？）。
手动进奖励页看每日阅读进度实际值。"""
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
    if any(k in t for k in ("已获赠币", "再读", "领取", "分钟")):
        print(f"y={b[1]:4d} x={b[0]:4d} w={b[2]:3d} | {t}", flush=True)
client.close()
