"""页面是 AI朗读播放页（第349章 00:38/07:26 播放中，II 暂停按钮 (333,489)）。
听书自动播放到第349章了。策略最终敲定：
**就在这页暂停听书（点 II）→ 找「查看原文」进正文 → 开自动阅读。**
昨天验证过「查看原文」在 (440,1102) 附近。执行。"""
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
client.swipe(333, 489, 333, 489, 60)  # 暂停
time.sleep(2)
s = client.screencap()
orig = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes() if "查看原文" in t]
if orig:
    t, b = orig[0]
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(3.5)
    s2 = client.screencap()
    texts = client.recognize("OCR", {}, s2).all_texts()
    print("正文:", " | ".join(texts[:5])[:110], flush=True)
else:
    print("无查看原文，OCR 全页:", flush=True)
    for t, b in sorted(boxes, key=lambda x: x[1][1])[:10]:
        print(f"y={b[1]:4d} x={b[0]:4d} | {t}", flush=True)
client.close()
