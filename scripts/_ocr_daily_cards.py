"""回顶成功，但「每日阅读/听书」卡还在更下方（签到卡后面）。
下滑一屏 OCR 找这两张卡。"""
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
client.swipe(360, 1000, 360, 420, 600)
time.sleep(2)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
for t, b in sorted(boxes, key=lambda x: x[1][1]):
    if any(k in t for k in ("阅读", "听书", "再读", "再听", "分钟", "领", "去", "赠币", "时长")):
        print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
