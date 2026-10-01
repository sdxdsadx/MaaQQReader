"""「今日已获赠币」后面数字没读出（金额可能分行/在右侧大字）。改读全部
文本找数字行，并截图存档。同时确认两次点击是否生效（有无「已领取」变化）。"""
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
boxes = client.recognize("OCR", {}, s).text_boxes()
for t, b in sorted(boxes, key=lambda x: x[1][1])[:24]:
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
