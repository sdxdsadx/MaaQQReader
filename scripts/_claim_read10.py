"""✅ 听书 +20 领到：赠币 204→224！
现在处理阅读：页面显示「今日再读6分钟领20赠币」（用户说的 24 分钟
以实际页面为准=还差6分钟），下面有 10分钟/30分钟 两档时长兑赠币的
「领取」按钮。先试点 10 分钟档「领取」看是否可领（可能之前已达标）。"""
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
# 阅读时长兑赠币 10分钟档 领取按钮 (198,480)→中心 (198+30, 480+20)
client.swipe(228, 500, 228, 500, 60)
time.sleep(3)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
for t, b in sorted(boxes, key=lambda x: x[1][1])[:14]:
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
