"""「今日再读N分钟领20赠币」行没出现在过滤里——往上滑一点看该条目完整状态。
同时注意：**「每周阅读600分钟+100赠币 立即领取 已读600分钟」可领！**
先把每周 100 赞领了（点 立即领取 y=722），再看阅读条目。"""
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
# 每周 600 分钟奖励领取
s = client.screencap()
for t, b in client.recognize("OCR", {}, s).text_boxes():
    if "立即领取" in t and b[1] > 650:
        x, y = b[0] + b[2] // 2, b[1] + b[3] // 2
        print(f"点每周领取 @ ({x},{y})", flush=True)
        client.swipe(x, y, x, y, 80)
        break
time.sleep(3)
# 回顶部找「今日再读」条目
client.swipe(360, 700, 360, 1200, 500)
time.sleep(2)
s2 = client.screencap()
for t, b in sorted(client.recognize("OCR", {}, s2).text_boxes(), key=lambda x: x[1][1]):
    if any(k in t for k in ("已获赠币", "再读", "阅读", "去阅读", "分钟")):
        print(f"y={b[1]:4d} | {t}", flush=True)
client.close()
