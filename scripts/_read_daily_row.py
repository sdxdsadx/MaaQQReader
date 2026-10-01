"""「每日阅读领赠币」条目在 y≈474-698 之间被截断（再读N分钟那行没进 OCR
前 12 条）。精确下滑到该卡片区。另外「每周+100 已领」已确认。
只补一件事：把「今日再读N分钟」当前值读出来。"""
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
# 从当前位置（每周卡在 y777）往下微滑 250px，让每日阅读卡完整入镜
client.swipe(360, 900, 360, 650, 400)
time.sleep(2)
s = client.screencap()
for t, b in sorted(client.recognize("OCR", {}, s).text_boxes(), key=lambda x: x[1][1]):
    if any(k in t for k in ("阅读", "再读", "分钟", "领取", "去")):
        print(f"y={b[1]:4d} x={b[0]:4d} | {t}", flush=True)
client.close()
