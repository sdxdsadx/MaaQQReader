"""ORES/immny 是乱码 OCR（正文被翻到听书/漫画页？或者点击把页面点乱了：
呼菜单→设置点(452,1247)在当前页面布局下点错位置（比如当前已不在正文页
而在书城/简介页）。实时看一下现在屏幕状态。"""
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
for t, b in sorted(boxes, key=lambda x: x[1][1])[:16]:
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
