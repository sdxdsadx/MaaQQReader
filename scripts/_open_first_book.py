"""重大进展：书架页显示「再读1分钟领20赠币」——只差 1 分钟！
（重启前的两轮挂机累计了 9 分钟有效阅读。）
开书进正文 → 跑 auto_read 2 分钟即可达标。先点开第一本书进正文。"""
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
# 点第一本书（笔记行下方的书名，通常 y≈440-500）
book = [(t, b) for t, b in boxes if 400 < b[1] < 560 and b[2] > 100]
print("书候选:", book[:2], flush=True)
if book:
    t, b = book[0]
    client.swipe(b[0] + 40, b[1] + 10, b[0] + 40, b[1] + 10, 60)
    time.sleep(3.5)
    s2 = client.screencap()
    texts = client.recognize("OCR", {}, s2).all_texts()
    print("进入:", " | ".join(texts[:6])[:130], flush=True)
client.close()
