"""书架页：今日阅读进度「再读7分钟领20赠币」——35 分钟挂机只累计了 3 分钟
有效阅读（同昨天规律：挂机不被全记）。「全职法师 正在播放第342章」说明
听书还在后台播放。
入口「再读7分钟领20赠币>」y=194——点它进奖励页。"""
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
client.swipe(154, 204, 154, 204, 60)
time.sleep(3)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
for t, b in sorted(boxes, key=lambda x: x[1][1]):
    if any(k in t for k in ("已获赠币", "再读", "已读", "听书", "已听", "领取", "分钟")):
        print(f"y={b[1]:4d} x={b[0]:4d} w={b[2]:3d} | {t}", flush=True)
client.close()
