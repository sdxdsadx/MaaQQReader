"""进入了「进度跳转」确认页（是否同步上次阅读进度：第230章）。
点「跳转」确认 → 进正文 → 启动 300 分钟看护。"""
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
jump = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes() if "跳转" in t]
if jump:
    t, b = jump[-1]
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(3.5)
s2 = client.screencap()
texts = client.recognize("OCR", {}, s2).all_texts()
print("正文:", " | ".join(texts[:6])[:130], flush=True)
client.close()
