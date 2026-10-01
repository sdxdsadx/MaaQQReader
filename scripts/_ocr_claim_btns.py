"""页面无变化（10分钟档领取后没弹成功、赠币仍 224）——点 (228,500) 可能
落在按钮外。按钮 box 从 OCR：领取@(198,480) 文本中心≈(198+30,480+20)=(228,500)
应该对。但 +20 标签 (198,357) 在上方——布局：+20 y=357 是「读10分钟得20」
进度条上的？重新精确定位：截屏裁剪 y 430..520 区域放大 OCR，拿按钮准确 box。"""
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
boxes = client.recognize("OCR", {"roi": [0, 340, 720, 200]}, s).text_boxes()
for t, b in sorted(boxes, key=lambda x: x[1][1]):
    print(f"y={b[1]:4d} x={b[0]:4d} w={b[2]:3d} h={b[3]:3d} | {t}")
client.close()
