"""右上图标没反应（页面没变）。换最直接的路：回书架找「书架」顶部听书
入口或重新让听书浮窗出现。先点左上返回箭头 (25,56) 回上一层。"""
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
client.swipe(25, 56, 25, 56, 60)
time.sleep(2.5)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
print("返回后:", flush=True)
for t, b in sorted(boxes, key=lambda x: x[1][1])[:16]:
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}", flush=True)
client.close()
