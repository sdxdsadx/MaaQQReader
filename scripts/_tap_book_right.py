"""简介页没有「继续阅读」按钮（这本是听书详情页）。
终极方案（不再绕）：BACK 一次回书架 → 用 MAA pipeline 旧链入口
「RewardGotoReading/ReadingGotoShelf」那套：书架页底部有「再读N分钟领20赠币>」
昨天点它进的是奖励页；但正文入口=直接点书封面图（昨天 16:16 那次成功
是点 (173,452) 书名）→ 这本书点 (180,455)。
换一个更稳的：点书架右上「续读」图标（昨天 OCR 见过 35章/372章 行）。
执行：BACK → 书架 → OCR 找 全职法师 行 → 点它右侧的进度文字（35章/372章）。"""
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

adb = r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe"
dev = "127.0.0.1:16384"

from qqreader.config import load_config
from qqreader.maa.factory import build_maa_client

config = load_config("configs/qqreader.local.json")
client = build_maa_client(config)
client.connect()
subprocess.run([adb, "-s", dev, "shell", "input", "keyevent", "4"],
               capture_output=True, timeout=15)
time.sleep(2.5)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
qz = [(t, b) for t, b in boxes if "全职法师" in t]
print("书行:", qz, flush=True)
if qz:
    t, b = qz[0]
    # 点书名右侧 100px（进度/继续阅读热区）
    client.swipe(b[0] + 150, b[1] + 15, b[0] + 150, b[1] + 15, 60)
    time.sleep(4)
    s2 = client.screencap()
    texts = client.recognize("OCR", {}, s2).all_texts()
    print("进入:", " | ".join(texts[:6])[:120], flush=True)
client.close()
