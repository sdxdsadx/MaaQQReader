"""当前在奖励页下半部（外部任务区）。每日阅读/听书卡在上半部（y<400），
需要上滑。上滑后 OCR。"""
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
client.swipe(360, 950, 360, 350, 500)
time.sleep(2)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
for t, b in sorted(boxes, key=lambda x: x[1][1]):
    if any(k in t for k in ("再读", "听书", "阅读", "分钟", "已领", "领取", "去")):
        print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
