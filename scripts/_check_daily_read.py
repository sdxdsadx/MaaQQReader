"""✅ 每周 600 分钟奖 +100 已领：赠币 204→304！
现在看「每日阅读领赠币」条目（今日再读 N 分钟）状态——还在往下一点。"""
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
client.swipe(360, 1000, 360, 600, 500)
time.sleep(2)
s = client.screencap()
for t, b in sorted(client.recognize("OCR", {}, s).text_boxes(), key=lambda x: x[1][1]):
    if any(k in t for k in ("阅读", "再读", "领取", "去阅读", "赠币")):
        print(f"y={b[1]:4d} x={b[0]:4d} | {t}", flush=True)
client.close()
