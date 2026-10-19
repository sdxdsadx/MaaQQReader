"""状态明确：
- 10分钟档「已领取」✅
- 30分钟档「领取」可点（y=528 x=484）→ 今日阅读已过 30 分钟？「再读15分钟」
  是下一档（45分钟档）的意思？不对——「今日再读15分钟领20赠币」=还差15
  才到下一档。30分钟档按钮可点=30分钟已达标（15+15+35min挂机部分计入）。
- 听书卡没显示按钮（可能已领）。
点 30 分钟档领取，然后查听书按钮。"""
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
    return "?"

client.swipe(502, 541, 502, 541, 60)
time.sleep(2.5)
print("30分钟档后:", coins(), flush=True)
# 下滑找听书按钮
client.swipe(360, 1000, 360, 600, 500)
time.sleep(2)
s = client.screencap()
for t, b in sorted(client.recognize("OCR", {}, s).text_boxes(), key=lambda x: x[1][1]):
    if "听书" in t or "已听" in t or "立即领取" in t:
        print(f"y={b[1]:4d} x={b[0]:4d} w={b[2]:3d} | {t}", flush=True)
client.close()
