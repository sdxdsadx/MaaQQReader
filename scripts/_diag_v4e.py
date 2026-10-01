"""对刚截的活体书城页全屏 OCR——看底部导航有没有「书城/书架」，确定 HOME 特征该加什么。"""
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
ocr = client.recognize("OCR", {}, s)
d = ocr.detail if isinstance(ocr.detail, dict) else {}
items = d.get("all") or d.get("boxes") or d.get("items") or []
print("=== 活体书城页 OCR（全部）===")
for it in items:
    if isinstance(it, dict):
        box = it.get("box") or []
        y = box[1] if len(box) > 1 else -1
        print(f"y={y:4d} | {it.get('text')}")
client.close()
