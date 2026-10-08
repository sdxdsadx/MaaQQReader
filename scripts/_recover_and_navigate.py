"""模拟器+QQ阅读已恢复（pid 2494）。导航：跳过开屏 → 点全职法师续读行
进正文 → 启动滑动翻页补时（60 分钟滑动 ≈ 30 分钟有效，覆盖缺口）。"""
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
s = client.screencap()
skip = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes() if "跳过" in t]
if skip:
    t, b = skip[0]
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(3)
    print("跳过开屏", flush=True)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
progress = [(t, b) for t, b in boxes if "3385" in t]
print("全职法师续读行:", progress, flush=True)
if progress:
    t, b = progress[0]
    client.swipe(b[0] + 60, b[1] + 10, b[0] + 60, b[1] + 10, 60)
    time.sleep(4)
    s2 = client.screencap()
    boxes2 = client.recognize("OCR", {}, s2).text_boxes()
    body = [(t, b) for t, b in boxes2 if 100 < b[1] < 1000 and b[2] > 200 and len(t) > 12]
    print("正文判断:", len(body) >= 2, flush=True)
client.close()
