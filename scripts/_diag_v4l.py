"""奖励页全页 OCR——找「看小视频领好礼」广告卡位置（v4k 没打到？页面上半部分）。
顺便确认赠币基线 156。"""
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
s = client.screencap()
ocr = client.recognize("OCR", {}, s)
boxes = ocr.text_boxes()
print("=== 奖励页全部 OCR（按 y 排序，前 30）===")
for t, b in sorted(boxes, key=lambda x: x[1][1])[:30]:
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
