"""9 分钟挂机 SUCCESS + 时长涨到 603 分钟（+3？），但赠币仍 204。
「今日再读6分钟领20赠币」——之前显示 6，读 9 分钟后应该已达标！
去奖励页中部看「每日阅读领赠币」条目现在的状态（应变为可领取/已领取）。"""
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
client.swipe(360, 1000, 360, 550, 500)
time.sleep(2)
s = client.screencap()
for t, b in sorted(client.recognize("OCR", {}, s).text_boxes(), key=lambda x: x[1][1]):
    if any(k in t for k in ("阅读", "领取", "分钟", "赠币", "已领")):
        print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
