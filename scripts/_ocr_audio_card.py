"""阅读档位领取无变化（120 不动——今天有效阅读 3 分钟没到 10 分钟档，
按钮是灰态，点不动，正常）。听书卡：已听 126 分钟 ≥30 分钟——但没看到
「领取/立即领取」按钮行。下滑一点看听书卡按钮状态。"""
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
boxes = client.recognize("OCR", {}, s).text_boxes()
for t, b in sorted(boxes, key=lambda x: x[1][1]):
    if 550 <= b[1] <= 780:
        print(f"y={b[1]:4d} x={b[0]:4d} w={b[2]:3d} | {t}", flush=True)
client.close()
