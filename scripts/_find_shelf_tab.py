"""点 (89,1263) 没切到书架——当前还在书城分类页（月票榜/全职法师63名）。
底部导航可能被分类页内容变化影响。直接 OCR 底部 y>1200 找「书架」。"""
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
for attempt in range(3):
    s = client.screencap()
    boxes = client.recognize("OCR", {}, s).text_boxes()
    shelf = [(t, b) for t, b in boxes if "书架" in t and b[1] > 1150]
    print(f"[{attempt}] 底部书架tab:", shelf, flush=True)
    if shelf:
        t, b = shelf[0]
        x, y = b[0] + b[2] // 2, b[1] + b[3] // 2
        client.swipe(x, y, x, y, 60)
        time.sleep(2.5)
        s2 = client.screencap()
        allb = client.recognize("OCR", {}, s2).text_boxes()
        progress = [(t2, b2) for t2, b2 in allb if "章/" in t2]
        print("书架页续读行:", progress, flush=True)
        if progress:
            t2, b2 = progress[0]
            client.swipe(b2[0] + 60, b2[1] + 10, b2[0] + 60, b2[1] + 10, 60)
            time.sleep(3.5)
            s3 = client.screencap()
            texts = client.recognize("OCR", {}, s3).all_texts()
            print("进入:", " | ".join(texts[:6])[:130], flush=True)
        break
    time.sleep(1)
client.close()
