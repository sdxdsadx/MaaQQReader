"""更新安装页已退出（BACK），app 回到书城页。继续：书架 → 奖励页 → 清领取。
（刚才书架点击无效的真凶=安装授权页弹在后面拦截了焦点。）"""
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
    client.swipe(360, 1050, 360, 500, 600)
    time.sleep(2)
    for _ in range(6):
        boxes = client.recognize("OCR", {}, client.screencap()).text_boxes()
        claim = [(t, b) for t, b in boxes if t.strip() == "领取"]
        if not claim:
            print("无可领按钮，停", flush=True)
            break
        t, b = claim[0]
        client.swipe(b[0] + b[2] // 2, b[1] + b[3] // 2, b[0] + b[2] // 2, b[1] + b[3] // 2, 60)
        time.sleep(2.5)
        print("领取后:", coins(), flush=True)
        client.swipe(360, 1100, 360, 700, 400)
        time.sleep(1.5)
client.close()
