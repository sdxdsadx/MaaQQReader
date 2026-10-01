"""看每日阅读卡和听书卡当前状态（需要到奖励页中部）。直接全页 OCR 找
「再读N分钟」「听书」相关行。"""
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
for t, b in sorted(boxes, key=lambda x: x[1][1]):
    if any(k in t for k in ("再读", "听书", "阅读", "分钟", "领", "去")):
        print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
