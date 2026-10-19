"""当前页是抽奖区（已到底往上2屏），看到「回到顶部」入口 y=1229。
点它直接回奖励页顶部，看「每日阅读领赠币」「每日听书N分钟」卡片实时状态
（用户说：听书币没领到 + 阅读还需24分钟）。"""
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
client.swipe(312, 1229, 312, 1229, 60)
time.sleep(2.5)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
for t, b in sorted(boxes, key=lambda x: x[1][1])[:22]:
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
