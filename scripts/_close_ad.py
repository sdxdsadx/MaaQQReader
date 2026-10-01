"""「奖励已领取 跳过」「恭喜提前获得奖励」——广告奖励已发！点「跳过」关闭。
这证明：跳过→(详情页|确认框)→退出后奖励照发（提前领奖机制）。
整链已通。点跳过收尾。"""
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
    if "跳过" in t:
        x, y = b[0] + b[2] // 2, b[1] + b[3] // 2
        print(f"点跳过 @ ({x},{y})")
        client.swipe(x, y, x, y, 60)
        break
time.sleep(3)
s2 = client.screencap()
texts = client.recognize("OCR", {}, s2).all_texts()
print("现在:", " | ".join(texts[:8])[:150])
client.close()
