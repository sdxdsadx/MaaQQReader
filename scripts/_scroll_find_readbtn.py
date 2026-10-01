"""BACK 进了华娱书的简介页。乱跳。停用手动导航——直接用
DirectReadingFlow 的第一段：跑 run_task 但把挂机时间改回 1 分钟？
不行，等 Codex。更简单：**当前简介页有「继续阅读」按钮吗**——
往下滚动看按钮区（简介页底部有 继续阅读/免费阅读 按钮）。"""
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
client.swipe(360, 1000, 360, 300, 400)
time.sleep(1.5)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
btn = [(t, b) for t, b in boxes if any(k in t for k in ("阅读", "听书", "免费"))]
print("底部按钮:", btn, flush=True)
if btn:
    t, b = btn[0]
    x, y = b[0] + b[2] // 2, b[1] + b[3] // 2
    print(f"点 {t} @ ({x},{y})", flush=True)
    client.swipe(x, y, x, y, 60)
    time.sleep(3.5)
    s2 = client.screencap()
    texts = client.recognize("OCR", {}, s2).all_texts()
    print("进入:", " | ".join(texts[:5])[:120], flush=True)
client.close()
