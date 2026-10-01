"""重启后落在书城页（男生频道）。这正是 issue #13/#14 修的场景——
手动点底部「书架」tab (89,1263) 回书架，再点时长兑赠币入口。"""
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
    return None

client.swipe(89, 1263, 89, 1263, 60)
time.sleep(2.5)
s = client.screencap()
entry = [(t, b) for t, b in client.recognize("OCR", {}, s).text_boxes()
         if "兑赠币" in t or "领20赠币" in t]
print("书架入口:", entry, flush=True)
if entry:
    t, b = entry[-1]
    client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
    time.sleep(4)
    print("奖励页:", coins(), flush=True)

    # 下滑到阅读档位区，把所有可领的「领取」按钮全点一遍
    client.swipe(360, 1050, 360, 500, 600)
    time.sleep(2)
    for _ in range(6):
        boxes = client.recognize("OCR", {}, client.screencap()).text_boxes()
        claim = [(t, b) for t, b in boxes if t.strip() == "领取"]
        if not claim:
            break
        t, b = claim[0]
        client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
        time.sleep(2.5)
        print("已点领取:", coins(), flush=True)
        client.swipe(360, 1100, 360, 700, 400)
        time.sleep(1.5)
client.close()
