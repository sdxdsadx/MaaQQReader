"""点全职法师后没进正文（弹了什么又回书架，本周时长已 44 分钟）。
当前书架页。再点一次全职法师（这次点续读进度行）。"""
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
qz = [(t, b) for t, b in boxes if "全职法师" in t]
prog = [(t, b) for t, b in boxes if "章/" in t]
print("书:", qz, "进度行:", prog, flush=True)
target = prog[0] if prog else qz[0]
t, b = target
client.swipe(b[0] + 60, b[1] + 10, b[0] + 60, b[1] + 10, 60)
time.sleep(3.5)
s2 = client.screencap()
texts = client.recognize("OCR", {}, s2).all_texts()
print("进入:", " | ".join(texts[:6])[:120], flush=True)
client.close()
