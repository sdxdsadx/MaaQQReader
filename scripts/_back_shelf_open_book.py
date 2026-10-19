"""页面顶部「AI朗读」标题——还在朗读的书籍信息页（刚才简介页是听书面板）。
BACK 回上一层，找正文入口。之前成功路径：书架点书名直接进正文。
重新来：BACK×2 回书架 → 点书名（不是进度行）→ 若直接进正文即可。"""
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
subprocess.run([adb, "-s", dev, "shell", "input", "keyevent", "4"],
               capture_output=True, timeout=15)
time.sleep(2.5)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
qz = [(t, b) for t, b in boxes if "全职法师" in t]
print("书架全职法师:", qz, flush=True)
if qz:
    t, b = qz[0]
    client.swipe(b[0] + 50, b[1] + 15, b[0] + 50, b[1] + 15, 60)
    time.sleep(4)
    s2 = client.screencap()
    texts = client.recognize("OCR", {}, s2).all_texts()
    print("进入:", " | ".join(texts[:6])[:120], flush=True)
client.close()
