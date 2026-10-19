"""书城页判 UNKNOWN（#10 修复后新卡点）：书城页底部有「书城」tab 而无
「书架」？看完整 OCR 底部导航 + HOME 定义需要什么。之前书城页 OCR 含
y=1250 书架+书城。打印 y>1100 的全部行。"""
import sys
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
boxes = client.recognize("OCR", {}, s).text_boxes()
print("=== y>=1100 ===")
for t, b in sorted(boxes, key=lambda x: x[1][1]):
    if b[1] >= 1100:
        print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
