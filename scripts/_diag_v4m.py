"""奖励页下半部分 OCR（y>700）——找「看小视频领好礼」广告卡。"""
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
ocr = client.recognize("OCR", {}, s)
boxes = ocr.text_boxes()
print("=== y>=700 的 OCR ===")
for t, b in sorted(boxes, key=lambda x: x[1][1]):
    if b[1] >= 700:
        print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
