"""BACK 后进了书友榜而不是书架——这书正文页点中央区域是章评/书友浮层，
BACK 一次退浮层。再 BACK 一次应该到正文或书架。连续退出到书架：最多 4 次
BACK，每次后检查是否有「书架」标记，到书架就停。"""
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

for i in range(5):
    s = client.screencap()
    boxes = client.recognize("OCR", {}, s).text_boxes()
    on_shelf = any(t.strip() == "书架" and b[1] < 100 for t, b in boxes)
    if on_shelf:
        print(f"[{i}] 已到书架页", flush=True)
        break
    subprocess.run([adb, "-s", dev, "shell", "input", "keyevent", "4"],
                   capture_output=True, timeout=15)
    time.sleep(2)
    print(f"[{i}] BACK", flush=True)

s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
entry = [(t, b) for t, b in boxes if "兑赠币" in t or "领20赠币" in t]
print("入口:", entry, flush=True)
if entry:
    t, b = entry[-1]
    client.swipe(b[0] + 100, b[1] + 10, b[0] + 100, b[1] + 10, 60)
    time.sleep(3)
    s2 = client.screencap()
    for t2, b2 in sorted(client.recognize("OCR", {}, s2).text_boxes(),
                         key=lambda x: x[1][1]):
        if any(k in t2 for k in ("已获赠币", "再读", "领取", "分钟")):
            print(f"y={b2[1]:4d} x={b2[0]:4d} w={b2[2]:3d} | {t2}", flush=True)
client.close()
