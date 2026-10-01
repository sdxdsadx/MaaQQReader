"""点浮窗展开了听书控制条（定时/倍速/下载/加书架/朗读人·曹操/查看原文/
372章）——这是听书播放面板，底部有「书籍简介」。面板里应该有暂停/关闭。
找「关闭/停止/退出」按钮：当前 OCR 没直接看到。听书面板通常左侧有暂停
按钮和 X。截全屏看完整面板。"""
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
    print(f"y={b[1]:4d} x={b[0]:4d} w={b[2]:3d} | {t}")
client.close()
