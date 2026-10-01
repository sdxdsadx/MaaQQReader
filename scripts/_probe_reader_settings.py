"""菜单已呼出：底部有「目录(y=1237,x=72) 进度(x=251) 设置(x=432) 书评区(x=604)」。
点「设置」(452,1247) → OCR 设置面板找「自动阅读」开关。"""
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
client.swipe(452, 1247, 452, 1247, 60)
time.sleep(2)
s = client.screencap()
boxes = client.recognize("OCR", {}, s).text_boxes()
for t, b in sorted(boxes, key=lambda x: x[1][1]):
    print(f"y={b[1]:4d} x={b[0]:4d} | {t}")
client.close()
