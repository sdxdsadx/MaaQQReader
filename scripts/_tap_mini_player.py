"""还在正文页——BACK 都被什么吃了？页面顶部有"く"返回箭头 (25,56)。
点它返回。同时注意右上"111"(x=693,y=110) 是听书悬浮图标残留！
它可能就是迷你播放器，点它进朗读页。两步：①点左上返回箭头回书架
②若仍在正文则再点。优先试：点右上角 111 图标 (693,115) 看反应。"""
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
client.swipe(693, 115, 693, 115, 60)   # 右上迷你播放器图标
time.sleep(2.5)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
print("点右上图标后:", flush=True)
for t, b in sorted(boxes, key=lambda x: x[1][1])[:18]:
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}", flush=True)
client.close()
