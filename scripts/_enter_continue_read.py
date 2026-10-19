"""进的是「书籍简介」页（全职法师，显示 朗读人·曹操）。需要点「继续阅读」
或正文入口。OCR 找阅读按钮。"""
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
btn = [(t, b) for t, b in boxes if any(k in t for k in ("继续阅读", "开始阅读", "免费听", "第342章", "目录"))]
print("按钮:", btn, flush=True)
target = [(t, b) for t, b in btn if "阅读" in t or "第342章" in t]
if target:
    t, b = target[0]
    x, y = b[0] + b[2] // 2, b[1] + b[3] // 2
    print(f"点 {t} @ ({x},{y})", flush=True)
    client.swipe(x, y, x, y, 60)
    time.sleep(3.5)
    s2 = client.screencap()
    texts = client.recognize("OCR", {}, s2).all_texts()
    print("进入:", " | ".join(texts[:6])[:130], flush=True)
client.close()
