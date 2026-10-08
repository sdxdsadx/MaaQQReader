"""7min 轮 SUCCESS 后回书架页。进奖励页读状态（时长兑赠币入口 y≈194）。"""
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
for t, b in client.recognize("OCR", {}, s).text_boxes():
    if "时长兑赠币" in t:
        x, y = b[0] + b[2] // 2, b[1] + b[3] // 2
        client.swipe(x, y, x, y, 80)
        print("点击入口")
        break
time.sleep(3)
client.swipe(360, 1000, 360, 550, 500)
time.sleep(2)
s2 = client.screencap()
for t, b in sorted(client.recognize("OCR", {}, s2).text_boxes(), key=lambda x: x[1][1]):
    if any(k in t for k in ("已获赠币", "再读", "已读", "领取", "分钟")):
        print(f"y={b[1]:4d} | {t}")
client.close()
