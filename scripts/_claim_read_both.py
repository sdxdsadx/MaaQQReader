"""精确 box：10分钟档「领取」@(199,481,w35,h21) → 中心 (216,491)。
30分钟档「领取」@(482,478,w39,h26) → 中心 (501,491)。
两个都点（先 10 分钟档），每点一次验证赠币变化。"""
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

def coins():
    s = client.screencap()
    for t, b in client.recognize("OCR", {}, s).text_boxes():
        if "今日已获赠币" in t:
            return t
    return "?"

print("before:", coins(), flush=True)
client.swipe(216, 491, 216, 491, 60)
time.sleep(3)
print("after10min:", coins(), flush=True)
client.swipe(501, 491, 501, 491, 60)
time.sleep(3)
print("after30min:", coins(), flush=True)
client.close()
