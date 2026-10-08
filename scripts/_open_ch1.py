"""目录页已开（华娱书，第1-9章）。点第1章进正文（这本书是新读的，从第1章
开始累计阅读时长一样有效）。然后跑 auto_read 5 分钟。"""
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
ch = [(t, b) for t, b in boxes if t.startswith("第1章")]
if ch:
    t, b = ch[0]
    x, y = b[0] + b[2] // 2, b[1] + b[3] // 2
    print(f"点 {t} @ ({x},{y})", flush=True)
    client.swipe(x, y, x, y, 60)
    time.sleep(3.5)
    s2 = client.screencap()
    texts = client.recognize("OCR", {}, s2).all_texts()
    print("正文:", " | ".join(texts[:6])[:130], flush=True)
client.close()
