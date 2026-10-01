"""点续读行进的是 AI 朗读播放页（第350章 II 可见）——**这本书的续读绑定
了听书模式**（用户之前用它听书）。正文入口在朗读页底部「查看原文」。
不再绕：朗读页 → 点「查看原文」→ 正文。之前这个按钮在 (494,1112)。
OCR 定位它点击。"""
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
orig = [(t, b) for t, b in boxes if "查看原文" in t]
print("查看原文:", orig, flush=True)
if orig:
    t, b = orig[0]
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(4)
    s2 = client.screencap()
    boxes2 = client.recognize("OCR", {}, s2).text_boxes()
    body = [(t, b) for t, b in boxes2 if 100 < b[1] < 1000 and b[2] > 200 and len(t) > 12]
    j = " ".join(t for t, b in boxes2)
    print("正文判断:", len(body) >= 2, "|", j[:90], flush=True)
client.close()
