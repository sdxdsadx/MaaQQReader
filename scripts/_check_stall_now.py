"""阅读翻页连续 stall——15:33 之后大量「未变」。可能又遇到章尾/弹窗。
活体 OCR 看页面。"""
import sys
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
for t, b in sorted(boxes, key=lambda x: x[1][1])[:10]:
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}", flush=True)
client.close()
