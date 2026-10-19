"""进了书籍简介页（朗读人·曹操 可见）。下滑到底找「继续阅读/开始阅读」
按钮进正文。"""
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
for i in range(3):
    s = client.screencap()
    boxes = client.recognize("OCR", {}, s).text_boxes()
    btn = [(t, b) for t, b in boxes
           if any(k in t for k in ("继续阅读", "开始阅读", "免费阅读"))]
    if btn:
        t, b = btn[0]
        print(f"按钮: {t} @ ({b[0]+b[2]//2},{b[1]+b[3]//2})", flush=True)
        client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
        time.sleep(3.5)
        s2 = client.screencap()
        texts = client.recognize("OCR", {}, s2).all_texts()
        print("进入:", " | ".join(texts[:5])[:110], flush=True)
        break
    client.swipe(360, 1100, 360, 400, 450)
    time.sleep(1.8)
else:
    print("未找到阅读按钮", flush=True)
client.close()
