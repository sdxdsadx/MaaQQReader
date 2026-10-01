"""点了章节名进了简介页而不是正文。简介页右上应有「开始阅读/免费阅读」
大按钮（通常在底部）。截全页找。另外注意：点「会员本书免费听」会启动听书
（又触发朗读会话！）——千万别点它。"""
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
