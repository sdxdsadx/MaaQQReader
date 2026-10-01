"""游戏已跑 25+ 分钟（02:47→03:13+）超过 20min 目标时长。run_task
DailyGameFlow timeout=40min。检查活体：游戏在线页还是卡在别处？"""
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
print(f"OCR {len(boxes)}:")
for t, b in sorted(boxes, key=lambda x: x[1][1])[:12]:
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
