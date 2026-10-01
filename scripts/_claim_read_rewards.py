"""奖励中心顶部可见：每日阅读领赠币(y=952) + 10分钟/30分钟档领取按钮
(y=1176)。「今日再读N分钟领20赠币」行在 y 952..1148 之间没读出来，
但用户说的两个相邻代币奖励应该就是这两个「领取」（10分钟档+30分钟档，
30 分钟阅读挂机后两个都该达标了）。
精确 box：领取1 (197,1176,w37)→中心(215,1189)；领取2 (483,1176,w37)→中心(501,1189)。
依次点击，每次后读赠币数验证。"""
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
    return "?(未见)"

print("before:", coins(), flush=True)
client.swipe(215, 1189, 215, 1189, 60)
time.sleep(3)
print("after#1:", coins(), flush=True)
client.swipe(501, 1189, 501, 1189, 60)
time.sleep(3)
print("after#2:", coins(), flush=True)
client.close()
