"""还在正文页。30 分钟弹窗可能已在 12:19 处理过（BACK）。
现在退出正文页回主页 → 进奖励中心领币。用返回箭头 (22,53)。"""
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
client.swipe(22, 53, 22, 53, 60)
time.sleep(2.5)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
for t, b in sorted(boxes, key=lambda x: x[1][1])[:14]:
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
