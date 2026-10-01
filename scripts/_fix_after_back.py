"""BACK 过头了？屏上只剩状态栏和一个 X（可能是弹窗）。截屏保存看。
点 X 关掉，然后看页面。"""
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
client.swipe(196, 1095, 196, 1095, 60)  # X 位置
time.sleep(2)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
print(f"OCR {len(boxes)}:")
for t, b in sorted(boxes, key=lambda x: x[1][1])[:12]:
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
