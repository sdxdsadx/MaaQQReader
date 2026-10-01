"""BACK 把我们带到了书城分类页（男生/出版听书漫画 + 会员榜/月票榜）。
正好——这是 issue #13 修复的 EnsureShelfOrGoto 应对场景！
但现在直接手动回书架更快：点底部导航「书架」(70,1250)。然后点续读行。"""
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
client.swipe(89, 1263, 89, 1263, 60)
time.sleep(2.5)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
progress = [(t, b) for t, b in boxes if "章/" in t]
print("续读行:", progress, flush=True)
if progress:
    t, b = progress[0]
    client.swipe(b[0] + 60, b[1] + 10, b[0] + 60, b[1] + 10, 60)
    time.sleep(3.5)
    s2 = client.screencap()
    texts = client.recognize("OCR", {}, s2).all_texts()
    print("进入:", " | ".join(texts[:6])[:130], flush=True)
client.close()
