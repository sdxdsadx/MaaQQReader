"""奖励页没有「看小视频领好礼」卡——可能在上方滚动 banner 或需下滑。
下滑一屏找广告卡（看小视频/立即观看）。"""
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
client.swipe(360, 1100, 360, 400, 600)
time.sleep(2.0)
s = client.screencap()
ocr = client.recognize("OCR", {}, s)
boxes = ocr.text_boxes()
print("=== 下滑后 OCR（含 视频/看/礼/广告/12）===")
for t, b in sorted(boxes, key=lambda x: x[1][1]):
    if any(k in t for k in ("视频", "礼物", "广告", "12", "看", "游戏")):
        print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
