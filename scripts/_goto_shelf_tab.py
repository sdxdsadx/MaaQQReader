"""手动导到书架页：底部导航「书架」y=1250 x=70（昨日 OCR 实证）。
先 OCR 底部导航确认当前位置有书架 tab，点击后 OCR 验证。"""
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
shelf = [(t, b) for t, b in boxes if "书架" in t and b[1] > 1100]
print("书架tab:", shelf, flush=True)
if shelf:
    t, b = shelf[0]
    x, y = b[0] + b[2] // 2, b[1] + b[3] // 2
    client.swipe(x, y, x, y, 60)
    time.sleep(2.5)
    s2 = client.screencap()
    texts = client.recognize("OCR", {}, s2).all_texts()
    print("点击后:", " | ".join(texts[:8])[:150], flush=True)
client.close()
