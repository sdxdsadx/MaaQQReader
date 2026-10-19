"""点「时长兑赠币」行中心无效（三次重试都在书架）——这个入口行可能是
「本周阅读时长/领赠币>」独立页入口，要点击整行或右侧箭头。
用昨天验证过的旧入口：「本周阅读时长/领赠币>」行尾 x≈540。或直接点
y=194 行的右端 (540,204)。再不行用 yesterday 脚本 _verify_reading_reward2
的坐标 (200,199)。试多点几个位置。"""
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

positions = [(540, 204), (100, 204), (280, 199), (165, 214)]
for pos in positions:
    if coins():
        break
    client.swipe(pos[0], pos[1], pos[0], pos[1], 60)
    time.sleep(3)
    print(f"点{pos}: {coins()}", flush=True)

client.close()
