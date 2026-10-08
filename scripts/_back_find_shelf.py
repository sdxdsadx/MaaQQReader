"""当前页是书城排行榜页，底部导航栏不见了（OCR 没扫到 y>1200 的 tab——
可能页面底部还有内容盖住导航，或这页是二级页无导航）。
务实做法：BACK 一次回书城主页 → 找书架 tab。"""
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
client.swipe(360, 640, 360, 640, 0)
time.sleep(2)
for attempt in range(2):
    s = client.screencap()
    boxes = client.recognize("OCR", {}, s).text_boxes()
    shelf = [(t, b) for t, b in boxes if "书架" in t and b[1] > 1100]
    print(f"[{attempt}] 书架tab:", shelf, flush=True)
    if shelf:
        t, b = shelf[0]
        x, y = b[0] + b[2] // 2, b[1] + b[3] // 2
        client.swipe(x, y, x, y, 60)
        time.sleep(2.5)
        s2 = client.screencap()
        allb = client.recognize("OCR", {}, s2).text_boxes()
        progress = [(t2, b2) for t2, b2 in allb if "章/" in t2]
        print("续读行:", progress, flush=True)
        if progress:
            t2, b2 = progress[0]
            client.swipe(b2[0] + 60, b2[1] + 10, b2[0] + 60, b2[1] + 10, 60)
            time.sleep(3.5)
            s3 = client.screencap()
            texts = client.recognize("OCR", {}, s3).all_texts()
            print("进入正文:", " | ".join(texts[:5])[:120], flush=True)
        break
    client.swipe(360, 640, 360, 640, 0)
    time.sleep(2)
client.close()
