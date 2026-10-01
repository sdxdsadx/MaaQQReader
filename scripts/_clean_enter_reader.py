"""重启后落书架（不是正文），但状态干净（听书会话已清）。
从书架点全职法师**续读行**（350章/3385章 y=488）——重启后点它会直接
进正文（不再接管听书，因为会话已清）。这是昨天 16:16 成功路径。"""
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
progress = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes() if "3385" in t]
print("续读行:", progress, flush=True)
t, b = progress[0]
client.swipe(b[0] + 60, b[1] + 10, b[0] + 60, b[1] + 10, 60)
time.sleep(4.5)
s2 = client.screencap()
boxes = client.recognize("OCR", {}, s2).text_boxes()
body = [(t, b) for t, b in boxes if 100 < b[1] < 1000 and b[2] > 200 and len(t) > 12]
j = " ".join(t for t, b in boxes)
print("正文判断:", len(body) >= 2, "|", j[:90], flush=True)
client.close()
