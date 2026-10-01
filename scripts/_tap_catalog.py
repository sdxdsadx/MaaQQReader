"""当前在书评/简介区（目录 可见）。点「目录」进目录页 → 点最新章节进正文。
或者更直接：找「继续阅读」类按钮。先点目录。"""
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
target = [(t, b) for t, b in boxes if t.strip() == "目录" or "继续阅读" in t or "开始阅读" in t]
print("目标:", target, flush=True)
if target:
    t, b = target[0]
    x, y = b[0] + b[2] // 2, b[1] + b[3] // 2
    client.swipe(x, y, x, y, 60)
    time.sleep(3)
    s2 = client.screencap()
    texts = client.recognize("OCR", {}, s2).all_texts()
    print("进入:", " | ".join(texts[:8])[:150], flush=True)
client.close()
