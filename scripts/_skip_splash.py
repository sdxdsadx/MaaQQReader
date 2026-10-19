"""app 重启后落在开屏活动页（奥德赛活动，右上角「跳过1」）。点跳过进主界面。"""
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
skip = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes() if "跳过" in t]
if skip:
    t, b = skip[0]
    x, y = b[0] + b[2] // 2, b[1] + b[3] // 2
    print(f"点跳过 @ ({x},{y})", flush=True)
    client.swipe(x, y, x, y, 60)
    time.sleep(3)
s2 = client.screencap()
texts = client.recognize("OCR", {}, s2).all_texts()
print("跳过后:", " | ".join(texts[:8])[:140], flush=True)
client.close()
