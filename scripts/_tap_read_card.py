"""还在书架页（点 y=199 没进奖励页——入口文案位置变了：y=166 领20赠币 /
y=190 再读10分钟领20赠币>）。这是书架页的阅读卡，入口是整卡点击。
点 y=190 行 (200,199) 没生效——可能需要点右侧箭头或者卡片下半。
改为点「领20赠币」(553+44, 165+13)=(597,178)。"""
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
client.swipe(597, 178, 597, 178, 60)
time.sleep(3)
s = client.screencap()
texts = client.recognize("OCR", {}, s).all_texts()
print("点击后:", " | ".join(texts[:10])[:170])
client.close()
