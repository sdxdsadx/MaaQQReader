"""Check 脚本空输出——可能当前屏不在奖励页（7min 挂机后停在正文/书架）。
打印当前页全部 OCR 判断位置。"""
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
print("OCR 条数:", len(boxes))
for t, b in sorted(boxes, key=lambda x: x[1][1])[:16]:
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
