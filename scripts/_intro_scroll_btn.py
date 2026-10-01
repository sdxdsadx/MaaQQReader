"""又落在书籍简介（听书面板）。这次听书会话已被 force-stop 清掉，
简介页下滑找「继续阅读/第348章」按钮进正文。上次下滑 3 次没找到
是因为进了「猜你喜欢听」区——这次滑一半就 OCR。"""
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
for i in range(5):
    s = client.screencap()
    boxes = client.recognize("OCR", {}, s).text_boxes()
    j = " ".join(t for t, b in boxes)
    btn = [(t, b) for t, b in boxes
           if any(k in t for k in ("继续阅读", "开始阅读", "免费阅读", "第348章", "阅读原文"))]
    if btn:
        t, b = btn[0]
        print(f"按钮: {t}", flush=True)
        client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
        time.sleep(4)
        s2 = client.screencap()
        texts = client.recognize("OCR", {}, s2).all_texts()
        print("进入:", " | ".join(texts[:5])[:110], flush=True)
        break
    client.swipe(360, 1050, 360, 550, 400)
    time.sleep(1.5)
    print(f"下滑{i+1}: {j[:60]}", flush=True)
client.close()
