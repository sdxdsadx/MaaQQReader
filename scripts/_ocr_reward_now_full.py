"""领取循环点了 5 次赠币不涨——查看点击的按钮到底在什么卡片上。
可能点的是灰态按钮（时长档虽显示 146 分钟，但档位要求「今日再读 N 分钟」
的 N 是从当前时刻往前算的连续阅读，而不是总时长！）。
或者点击的「领取」其实是其他卡（听书/每周）的灰态按钮。
停手，OCR 快照当前页面完整状态，人工判断。"""
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
    print(f"y={b[1]:4d} x={b[0]:4d} w={b[2]:3d} | {t}", flush=True)
client.close()
